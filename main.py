"""Briar & Burrow — a complete, asset-free Pygame metroidvania."""
from __future__ import annotations

import argparse
import array
import json
import math
import os
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parent
W, H = 960, 540


def clamp(value, low, high):
    return max(low, min(high, value))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke-test', action='store_true', help='Run deterministic gameplay checks and exit.')
    parser.add_argument('--headless', action='store_true', help='Use SDL dummy video/audio drivers.')
    parser.add_argument('--frames', type=int, default=0, help='Exit after N frames (0 means unlimited).')
    parser.add_argument('--screenshot', type=Path, help='Save the last rendered frame as a PNG.')
    parser.add_argument('--save-dir', type=Path, default=ROOT / 'saves')
    args = parser.parse_args()
    if args.headless or args.smoke_test:
        os.environ['SDL_VIDEODRIVER'] = 'dummy'
        os.environ['SDL_AUDIODRIVER'] = 'dummy'
    import pygame as pg
    pg.init()
    app = Game(pg, args)
    try:
        if args.smoke_test:
            app.smoke_test()
        else:
            app.run()
    finally:
        pg.quit()


ROOMS = {
    (0, 0): ('Whispering Canopy', 'forest', 'Branches remember every footstep.'),
    (1, 0): ('Wind Shrine', 'forest', 'The wind leaves a gift for small, brave things.'),
    (2, 0): ('Moonwell', 'blue', 'Even lost water finds its way home.'),
    (3, 0): ('Moth Observatory', 'blue', 'Someone once counted all these stars.'),
    (0, 1): ('Hearthburrow', 'forest', 'Your lantern will always be waiting.'),
    (1, 1): ('Moss Gallery', 'forest', 'Keep your claws sharp and your heart soft.'),
    (2, 1): ('Foxfire Crossing', 'ember', 'Follow the glow beneath the roots.'),
    (3, 1): ('Last Lantern', 'ember', 'Rest here. Something ancient is awake below.'),
    (0, 2): ('Root Cellar', 'blue', 'A whole world grows beneath the garden.'),
    (1, 2): ('Old Burrows', 'blue', 'Two little leaps can change everything.'),
    (2, 2): ('Briarworks', 'ember', 'These thorns drink the light.'),
    (3, 2): ('Heart of the Briar', 'ember', 'Bring the stolen seed back to the sun.'),
}
PALETTES = {
    'forest': ((12, 24, 32), (31, 63, 61), (57, 111, 85), (128, 208, 151)),
    'blue': ((12, 17, 36), (32, 43, 73), (60, 90, 115), (122, 195, 218)),
    'ember': ((29, 17, 33), (71, 39, 53), (117, 65, 67), (242, 172, 112)),
}
INK = (15, 23, 35)
CREAM = (242, 232, 205)
MUTED = (158, 178, 178)
GOLD = (243, 196, 114)
MINT = (131, 231, 196)
RED = (242, 112, 114)


class Game:
    def __init__(self, pg, args):
        self.pg, self.args = pg, args
        self.screen = pg.display.set_mode((1152, 648), pg.RESIZABLE)
        pg.display.set_caption('Briar & Burrow | A Weasel Metroidvania')
        self.canvas = pg.Surface((W, H))
        self.clock = pg.time.Clock()
        self.fonts = {size: pg.font.SysFont('segoeui,dejavusans,arial', size) for size in (12, 14, 16, 18, 22, 26, 32, 48, 64)}
        self.bold = pg.font.SysFont('georgia,dejavuserif', 56, bold=True)
        self.smallbold = pg.font.SysFont('segoeui,dejavusans', 18, bold=True)
        self.backgrounds = {}
        self.sounds = {}
        self.time = 0.0
        self.state = 'title'
        self.running = True
        self.fullscreen = False
        self.menu_selection = 0
        self.volume = True
        self.save_path = args.save_dir / 'progress.json'
        self.save_error = ''
        self.buttons = []
        self.shake = 0.0
        self.title_hint = ''
        self.make_sounds()
        self.reset()

    def make_sounds(self):
        pg = self.pg
        if not pg.mixer.get_init():
            return
        rate, _, channels = pg.mixer.get_init()
        for name, frequency, duration in [('jump', 420, .10), ('swing', 160, .09), ('hit', 90, .15), ('pickup', 720, .23), ('dash', 240, .12), ('save', 540, .30)]:
            samples = array.array('h')
            for i in range(int(rate * duration)):
                t = i / rate
                pitch = frequency * (1 + t * (3 if name in ('pickup', 'save') else -2))
                value = int(2600 * math.sin(2 * math.pi * pitch * t) * (1 - t / duration) ** 2)
                samples.extend([value] * channels)
            self.sounds[name] = pg.mixer.Sound(buffer=samples)

    def sound(self, name):
        if self.volume and name in self.sounds:
            self.sounds[name].play()

    def text(self, text, x, y, size=18, color=CREAM, center=False, font=None):
        surf = (font or self.fonts[size]).render(str(text), True, color)
        rect = surf.get_rect(midtop=(x, y)) if center else surf.get_rect(topleft=(x, y))
        self.canvas.blit(surf, rect)
        return rect

    def panel(self, rect, color=(18, 30, 42), border=(59, 82, 88), radius=12):
        self.pg.draw.rect(self.canvas, color, rect, border_radius=radius)
        self.pg.draw.rect(self.canvas, border, rect, 1, border_radius=radius)

    def reset(self):
        self.abilities = set()
        self.collected = set()
        self.visited = set()
        self.max_hp = 6
        self.hp = 6
        self.shards = 0
        self.boss_defeated = False
        self.checkpoint = (0, 1)
        self.particles = []
        self.projectiles = []
        self.attack_timer = 0.0
        self.attack_cooldown = 0.0
        self.attack_hits = set()
        self.invulnerable = 0.0
        self.dash_timer = 0.0
        self.dash_cooldown = 0.0
        self.dash_ready = True
        self.jump_buffer = 0.0
        self.coyote = 0.0
        self.jumps = 0
        self.facing = 1
        self.vx = self.vy = 0.0
        self.grounded = False
        self.toast = ''
        self.toast_timer = 0.0
        self.death_timer = 0.0
        self.boss = None
        self.enter_room((0, 1), 260, 430)

    @property
    def rect(self):
        return self.pg.Rect(round(self.x), round(self.y), 26, 42)

    def announce(self, message, duration=4):
        self.toast, self.toast_timer = message, duration

    def save(self):
        data = {'version': 1, 'abilities': sorted(self.abilities), 'collected': sorted(self.collected), 'visited': [list(r) for r in sorted(self.visited)], 'max_hp': self.max_hp, 'shards': self.shards, 'checkpoint': list(self.checkpoint), 'boss_defeated': self.boss_defeated}
        try:
            self.save_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.save_path.with_suffix('.tmp')
            temporary.write_text(json.dumps(data, indent=2), encoding='utf-8')
            temporary.replace(self.save_path)
            self.save_error = ''
            return True
        except OSError as error:
            self.save_error = f'Could not save: {error.strerror or "check folder permissions"}'
            self.announce(self.save_error, 7)
            return False

    def load(self):
        try:
            data = json.loads(self.save_path.read_text(encoding='utf-8'))
            if data.get('version') != 1:
                raise ValueError('Unsupported save version')
            checkpoint = tuple(data['checkpoint'])
            visited = {tuple(r) for r in data['visited']}
            abilities = set(data['abilities'])
            collected = set(data['collected'])
            hp = int(data['max_hp'])
            shards = int(data['shards'])
            if checkpoint not in ROOMS or not visited <= ROOMS.keys() or not abilities <= {'dash', 'double_jump'} or not 6 <= hp <= 8 or shards < 0:
                raise ValueError('Invalid save values')
            self.reset()
            self.checkpoint, self.visited = checkpoint, visited
            self.abilities, self.collected = abilities, collected
            self.max_hp = self.hp = hp
            self.shards = shards
            self.boss_defeated = bool(data.get('boss_defeated', False))
            self.enter_room(checkpoint, 260, 430)
            self.state = 'playing'
            self.announce('Welcome back, little wanderer.')
            return True
        except (OSError, ValueError, KeyError, TypeError):
            self.title_hint = 'Save could not be read. Start a new journey to begin again.'
            return False

    def enter_room(self, room, x, y):
        self.room = room
        self.visited.add(room)
        self.x, self.y = float(x), float(y)
        self.vx = self.vy = 0.0
        self.grounded = False
        self.jumps = 0
        self.dash_timer = 0
        self.dash_ready = True
        self.projectiles = []
        self.particles = []
        self.attack_hits = set()
        self.attack_timer = 0
        self.room_title_timer = 3.0
        self.transition_cooldown = .55
        # Every route is traversable with the basic jump. Abilities unlock marked doors.
        self.platforms = [self.pg.Rect(0, 480, W, 60), self.pg.Rect(170, 390, 150, 20), self.pg.Rect(390, 310, 160, 20), self.pg.Rect(650, 365, 155, 20)]
        if room == (3, 2):
            self.platforms = [self.pg.Rect(0, 480, W, 60), self.pg.Rect(95, 350, 140, 20), self.pg.Rect(725, 350, 140, 20)]
        self.enemies = []
        if room not in ((0, 1), (1, 0), (1, 2), (3, 1), (3, 2)):
            self.enemies = [dict(x=530., y=454., home=530., vx=62., hp=3, kind='crawler', hurt=0., id=0, attack=0.), dict(x=690., y=250., home=690., vx=-1., hp=2, kind='moth', hurt=0., id=1, attack=1.5)]
            if room[0] >= 2:
                self.enemies.append(dict(x=295., y=371., home=245., vx=48., hp=3, kind='crawler', hurt=0., id=2, attack=0.))
        self.boss = dict(x=685., y=392., hp=36, max_hp=36, mode='idle', timer=1.4, facing=-1, hurt=0., cycle=0) if room == (3, 2) and not self.boss_defeated else None

    def requirement(self, room):
        if room[0] == 3 and 'dash' not in self.abilities:
            return 'Wind Dash required — search the Wind Shrine above.'
        if room[1] == 2 and room[0] >= 2 and 'double_jump' not in self.abilities:
            return 'Double Leap required — search the Old Burrows below.'
        return ''

    def transition(self, target, x, y):
        if target not in ROOMS:
            return False
        if self.boss and self.boss['hp'] > 0:
            self.announce('The roots have sealed the arena. Defeat Thornback!')
            return False
        needed = self.requirement(target)
        if needed:
            self.announce(needed)
            return False
        self.enter_room(target, x, y)
        return True

    def portal_rect(self, direction):
        return self.pg.Rect(92 if direction == 'up' else 800, 399, 54, 81)

    def interact(self, direction=None):
        if self.transition_cooldown > 0:
            return
        col, row = self.room
        for name, delta in [('up', -1), ('down', 1)]:
            if direction not in (None, name):
                continue
            target = (col, row + delta)
            if target in ROOMS and self.rect.inflate(36, 12).colliderect(self.portal_rect(name)):
                self.transition(target, 119 if name == 'down' else 814, 432)
                return
        if self.room in ((0, 1), (3, 1)) and abs(self.rect.centerx - 270) < 70:
            self.checkpoint = self.room
            self.hp = self.max_hp
            if self.save():
                self.announce('Lantern kindled · health restored · journey saved')
                self.sound('save')
                self.burst(270, 410, GOLD, 25)
        elif direction is None:
            self.announce(ROOMS[self.room][2])

    def jump(self):
        if self.dash_timer > 0:
            return False
        if self.coyote > 0 or self.grounded:
            self.vy = -610
            self.jumps = 1
        elif 'double_jump' in self.abilities and self.jumps < 2:
            self.vy = -570
            self.jumps = 2
            self.burst(self.x + 13, self.y + 42, MINT, 14)
        else:
            return False
        self.grounded = False
        self.coyote = 0
        self.jump_buffer = 0
        self.sound('jump')
        return True

    def dash(self):
        if 'dash' in self.abilities and self.dash_cooldown <= 0 and self.dash_ready:
            self.dash_timer = .18
            self.dash_cooldown = .65
            self.dash_ready = False
            self.vy = 0
            self.invulnerable = max(self.invulnerable, .22)
            self.sound('dash')
            return True
        if 'dash' not in self.abilities:
            self.announce('Find the Wind Shrine to learn Wind Dash.', 2)
        return False

    def attack(self):
        if self.attack_cooldown <= 0:
            self.attack_timer = .22
            self.attack_cooldown = .33
            self.attack_hits = set()
            self.sound('swing')

    def attack_rect(self):
        return self.pg.Rect(self.x + (18 if self.facing > 0 else -67), self.y - 7, 75, 63)

    def damage(self, amount=1, source_x=None):
        if self.invulnerable > 0 or self.death_timer > 0:
            return
        self.hp = max(0, self.hp - amount)
        self.invulnerable = 1.1
        self.dash_timer = 0
        self.vy = -280
        self.vx = -260 if source_x is None or source_x > self.x else 260
        self.shake = .22
        self.sound('hit')
        self.burst(self.x + 13, self.y + 20, RED, 18)
        if self.hp <= 0:
            self.death_timer = 1.5

    def burst(self, x, y, color, count=10):
        for _ in range(count):
            self.particles.append([float(x), float(y), random.uniform(-145, 145), random.uniform(-185, 45), random.uniform(.25, .7), color])

    def pickup_info(self):
        if self.room == (1, 0):
            return 'dash', 470, 274, 'WIND DASH', 'Shift / K / X to dash. Cross the amber seals.'
        if self.room == (1, 2):
            return 'double_jump', 470, 274, 'DOUBLE LEAP', 'Press jump again in the air. The deep briars await.'
        if self.room in ((2, 0), (2, 2)):
            return f'heart_{self.room[0]}_{self.room[1]}', 727, 330, 'HEART OF THE HOLLOW', 'Maximum health increased. Every little heart matters.'
        return None

    def collect(self):
        info = self.pickup_info()
        if info and info[0] not in self.collected:
            key, x, y, title, subtitle = info
            if self.rect.inflate(8, 8).colliderect(self.pg.Rect(x - 15, y - 18, 30, 36)):
                self.collected.add(key)
                if key.startswith('heart'):
                    self.max_hp += 1
                else:
                    self.abilities.add(key)
                self.hp = self.max_hp
                self.burst(x, y, GOLD, 35)
                self.announce(f'{title} · {subtitle}', 7)
                self.sound('pickup')
                self.save()

    def update(self, dt, movement=0):
        self.time += dt
        for name in ('attack_timer', 'attack_cooldown', 'invulnerable', 'dash_cooldown', 'transition_cooldown', 'room_title_timer', 'toast_timer', 'shake', 'jump_buffer', 'coyote'):
            setattr(self, name, max(0, getattr(self, name) - dt))
        for p in self.particles[:]:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += 370 * dt
            p[4] -= dt
            if p[4] <= 0:
                self.particles.remove(p)
        if self.death_timer > 0:
            self.death_timer -= dt
            if self.death_timer <= 0:
                self.hp = self.max_hp
                self.enter_room(self.checkpoint, 260, 430)
                self.invulnerable = 1.5
                self.announce('The lantern calls you home. Your discoveries are safe.')
            return
        if self.jump_buffer > 0:
            self.jump()
        if self.dash_timer > 0:
            self.dash_timer = max(0, self.dash_timer - dt)
            self.vx = self.facing * 760
            self.vy = 0
            if random.random() < .65:
                self.burst(self.x + 13, self.y + 23, MINT, 1)
        else:
            target = movement * 245
            self.vx += clamp(target - self.vx, -1800 * dt, 1800 * dt)
            if movement:
                self.facing = 1 if movement > 0 else -1
            self.vy = min(900, self.vy + 1700 * dt)
        previous = self.rect
        self.x += self.vx * dt
        rect = self.rect
        for platform in self.platforms:
            if rect.colliderect(platform):
                if self.vx > 0:
                    self.x = platform.left - rect.width
                elif self.vx < 0:
                    self.x = platform.right
                rect = self.rect
        self.y += self.vy * dt
        rect = self.rect
        was_grounded = self.grounded
        self.grounded = False
        for platform in self.platforms:
            if rect.right > platform.left and rect.left < platform.right:
                # Use fractional position for floor contact so subpixel gravity
                # cannot make grounded flicker between integer Rect positions.
                if self.vy >= 0 and previous.bottom <= platform.top + 12 and self.y + rect.height >= platform.top:
                    self.y = platform.top - rect.height
                    self.vy = 0
                    self.grounded = True
                    self.coyote = .10
                    self.jumps = 0
                    self.dash_ready = True
                elif self.vy < 0 and rect.colliderect(platform):
                    self.y = platform.bottom
                    self.vy = 0
                rect = self.rect
        if was_grounded and not self.grounded:
            self.coyote = .10
            self.jumps = max(1, self.jumps)
        if self.y < 0:
            self.y, self.vy = 0., max(0, self.vy)
        if self.y > H + 80:
            self.damage(self.hp)
        if self.x < -12:
            if not self.transition((self.room[0] - 1, self.room[1]), W - 46, min(438, self.y)):
                self.x = 0
        elif self.x > W - 14:
            if not self.transition((self.room[0] + 1, self.room[1]), 20, min(438, self.y)):
                self.x = W - 26
        self.collect()
        self.update_enemies(dt)
        self.update_boss(dt)
        for shot in self.projectiles[:]:
            shot['x'] += shot['vx'] * dt
            shot['y'] += shot.get('vy', 0) * dt
            shot['life'] -= dt
            box = self.pg.Rect(shot['x'] - 9, shot['y'] - 9, 18, 18)
            if self.rect.colliderect(box):
                self.damage(1, shot['x'])
                self.projectiles.remove(shot)
            elif shot['life'] <= 0 or shot['x'] < -30 or shot['x'] > W + 30:
                self.projectiles.remove(shot)

    def update_enemies(self, dt):
        pg = self.pg
        for enemy in self.enemies[:]:
            enemy['hurt'] = max(0, enemy['hurt'] - dt)
            if enemy['kind'] == 'crawler':
                enemy['x'] += enemy['vx'] * dt
                if abs(enemy['x'] - enemy['home']) > 115:
                    enemy['vx'] = -enemy['vx']
                rect = pg.Rect(enemy['x'] - 17, enemy['y'] - 10, 34, 26)
            else:
                enemy['x'] = enemy['home'] + math.sin(self.time * 1.2) * 95
                enemy['y'] = 228 + math.sin(self.time * 2 + enemy['id']) * 42
                enemy['attack'] -= dt
                if enemy['attack'] <= 0 and abs(self.x - enemy['x']) < 430:
                    enemy['attack'] = 2.6
                    dx, dy = self.rect.centerx - enemy['x'], self.rect.centery - enemy['y']
                    length = max(1, math.hypot(dx, dy))
                    self.projectiles.append(dict(x=enemy['x'], y=enemy['y'], vx=dx / length * 140, vy=dy / length * 140, life=4, kind='spore'))
                rect = pg.Rect(enemy['x'] - 16, enemy['y'] - 16, 32, 32)
            if self.attack_timer > 0 and enemy['id'] not in self.attack_hits and self.attack_rect().colliderect(rect):
                self.attack_hits.add(enemy['id'])
                enemy['hp'] -= 1
                enemy['hurt'] = .18
                self.burst(*rect.center, GOLD, 9)
                self.sound('hit')
                if enemy['hp'] <= 0:
                    self.enemies.remove(enemy)
                    self.shards += 3
                    if self.shards % 9 == 0:
                        self.hp = min(self.max_hp, self.hp + 1)
                    self.burst(*rect.center, MINT, 18)
                    continue
            if self.rect.colliderect(rect):
                self.damage(1, rect.centerx)

    def update_boss(self, dt):
        boss = self.boss
        if not boss:
            return
        boss['timer'] -= dt
        boss['hurt'] = max(0, boss['hurt'] - dt)
        box = self.pg.Rect(boss['x'] - 72, boss['y'] - 2, 144, 90)
        if self.attack_timer > 0 and 'boss' not in self.attack_hits and self.attack_rect().colliderect(box):
            self.attack_hits.add('boss')
            boss['hp'] -= 1
            boss['hurt'] = .16
            self.burst(self.rect.centerx + self.facing * 35, self.rect.centery, GOLD, 12)
            self.sound('hit')
            if boss['hp'] <= 0:
                self.boss_defeated = True
                self.burst(boss['x'], 400, GOLD, 100)
                self.boss = None
                self.projectiles = []
                self.hp = self.max_hp
                self.shards += 50
                self.save()
                self.state = 'victory'
                return
        if boss['mode'] == 'idle' and boss['timer'] <= 0:
            boss['cycle'] += 1
            boss['facing'] = 1 if self.x > boss['x'] else -1
            boss['mode'] = 'warn_charge' if boss['cycle'] % 2 else 'warn_slam'
            boss['timer'] = .95 if boss['hp'] > 18 else .65
        elif boss['mode'] == 'warn_charge' and boss['timer'] <= 0:
            boss['mode'], boss['timer'] = 'charge', .9
            self.sound('dash')
        elif boss['mode'] == 'charge':
            boss['x'] += boss['facing'] * (400 if boss['hp'] > 18 else 520) * dt
            if boss['x'] <= 85 or boss['x'] >= W - 85 or boss['timer'] <= 0:
                boss['x'] = clamp(boss['x'], 85, W - 85)
                boss['mode'], boss['timer'] = 'idle', 1.1
                self.shake = .22
        elif boss['mode'] == 'warn_slam' and boss['timer'] <= 0:
            boss['mode'], boss['timer'] = 'idle', 1.4
            self.shake = .4
            for direction in (-1, 1):
                self.projectiles.append(dict(x=boss['x'], y=466., vx=direction * 270, life=4, kind='root'))
                if boss['hp'] <= 18:
                    self.projectiles.append(dict(x=boss['x'], y=423., vx=direction * 200, life=4, kind='root'))
            self.burst(boss['x'], 470, GOLD, 28)
            self.sound('hit')
        if self.rect.colliderect(box):
            self.damage(1, boss['x'])

    def background(self):
        pg = self.pg
        palette = PALETTES[ROOMS[self.room][1]]
        if self.room not in self.backgrounds:
            surface = pg.Surface((W, H))
            rng = random.Random(self.room[0] * 73 + self.room[1] * 199)
            for y in range(H):
                a = y / H
                color = tuple(int(palette[0][i] * (1 - a) + palette[1][i] * a) for i in range(3))
                pg.draw.line(surface, color, (0, y), (W, y))
            for layer in range(3):
                color = tuple(int(c * (.50 + layer * .16)) for c in palette[1])
                for _ in range(12):
                    x = rng.randrange(-40, W + 40)
                    width = rng.randrange(14, 38) + layer * 8
                    pg.draw.polygon(surface, color, [(x, H), (x + width, H), (x + width + 15, 0), (x - 20, 0)])
                    for _ in range(3):
                        y = rng.randrange(40, 370)
                        end = (x + rng.randrange(-110, 110), y - rng.randrange(20, 90))
                        pg.draw.line(surface, color, (x, y), end, max(3, width // 4))
            for _ in range(100):
                x, y = rng.randrange(W), rng.randrange(60, H)
                pg.draw.circle(surface, palette[1], (x, y), rng.choice([1, 1, 2]))
            self.backgrounds[self.room] = surface
        self.canvas.blit(self.backgrounds[self.room], (0, 0))
        # Slanted shafts, gently drifting spores and foreground grass.
        glow = pg.Surface((W, H), pg.SRCALPHA)
        for x in (180, 580):
            pg.draw.polygon(glow, (*palette[3], 8), [(x, 0), (x + 50, 0), (x + 230, 480), (x + 100, 480)])
        self.canvas.blit(glow, (0, 0))
        for i in range(28):
            x = (i * 137 + math.sin(self.time * .2 + i) * 25) % W
            y = (i * 61 - self.time * (8 + i % 4)) % 470
            pg.draw.circle(self.canvas, palette[3], (int(x), int(y)), 1 if i % 3 else 2)

    def draw_platforms(self):
        pg = self.pg
        palette = PALETTES[ROOMS[self.room][1]]
        for p in self.platforms:
            pg.draw.rect(self.canvas, (27, 34, 40), p)
            pg.draw.rect(self.canvas, palette[2], (p.x, p.y, p.w, 7))
            pg.draw.line(self.canvas, palette[3], (p.x, p.y), (p.right - 1, p.y), 2)
            for x in range(p.x + 9, p.right - 5, 29):
                pg.draw.line(self.canvas, palette[1], (x, p.y + 9), (x - 6, min(p.bottom, p.y + 25)), 2)
                pg.draw.line(self.canvas, palette[2], (x + 3, p.y + 2), (x + 7, p.y - (4 + x % 9)), 2)
            if p.h > 25:
                for x in range(12, W, 41):
                    pg.draw.circle(self.canvas, (43, 48, 47), (x, 504 + x % 21), 3)
        col, row = self.room
        for direction, delta in [('up', -1), ('down', 1)]:
            target = (col, row + delta)
            if target not in ROOMS:
                continue
            rect = self.portal_rect(direction)
            locked = bool(self.requirement(target))
            color = GOLD if locked else MINT
            pg.draw.rect(self.canvas, (15, 27, 33), rect, border_radius=26)
            pg.draw.rect(self.canvas, palette[2], rect, 5, border_radius=26)
            pg.draw.rect(self.canvas, color, rect.inflate(-14, -10), 1, border_radius=20)
            cx, cy = rect.centerx, rect.y + 34
            points = [(cx - 8, cy + 4), (cx, cy - 5), (cx + 8, cy + 4)] if direction == 'up' else [(cx - 8, cy - 4), (cx, cy + 5), (cx + 8, cy - 4)]
            pg.draw.lines(self.canvas, color, False, points, 2)
            self.text('W / E' if direction == 'up' else 'S / E', cx, rect.bottom - 23, 12, color, True)
            self.text('ASCEND' if direction == 'up' else 'DESCEND', cx, rect.y - 20, 12, MUTED, True)
        for dx in (-1, 1):
            target = (col + dx, row)
            if target in ROOMS:
                x = 8 if dx < 0 else W - 8
                locked = self.requirement(target)
                color = GOLD if locked else palette[3]
                if locked or self.boss:
                    for y in range(345, 479, 16):
                        pg.draw.line(self.canvas, color, (x - 6, y), (x + 6, y + 12), 3)
                else:
                    pg.draw.lines(self.canvas, color, False, [(x - dx * 4, 416), (x + dx * 1, 422), (x - dx * 4, 428)], 2)
        if self.room in ((0, 1), (3, 1)):
            x = 270
            pg.draw.rect(self.canvas, (85, 69, 55), (x - 4, 417, 8, 63))
            pg.draw.line(self.canvas, GOLD, (x - 14, 418), (x + 14, 418), 3)
            lamp = pg.Surface((80, 80), pg.SRCALPHA)
            for radius in range(32, 0, -2):
                pg.draw.circle(lamp, (*GOLD, 3 + (32 - radius) * 2), (40, 40), radius)
            self.canvas.blit(lamp, (x - 40, 375))
            pg.draw.rect(self.canvas, GOLD, (x - 7, 403, 14, 19), border_radius=4)
            self.text('E · REST & SAVE', x, 488, 12, GOLD, True)

    def draw_weasel(self, x, y, facing=1, moving=False, large=1):
        pg = self.pg
        sprite = pg.Surface((86, 68), pg.SRCALPHA)
        bob = round(math.sin(self.time * 16) * 2) if moving else round(math.sin(self.time * 3))
        brown, light = (158, 99, 65), (211, 158, 99)
        pg.draw.lines(sprite, (100, 64, 54), False, [(34, 42 + bob), (20, 45 + bob), (7, 38 + bob), (3, 28 + bob)], 10)
        pg.draw.circle(sprite, (53, 45, 45), (4, 29 + bob), 5)
        pg.draw.ellipse(sprite, brown, (30, 23 + bob, 32, 35))
        pg.draw.ellipse(sprite, CREAM, (43, 28 + bob, 17, 25))
        pg.draw.ellipse(sprite, brown, (44, 10 + bob, 26, 27))
        pg.draw.circle(sprite, light, (48, 14 + bob), 7)
        pg.draw.circle(sprite, (100, 57, 53), (48, 14 + bob), 3)
        pg.draw.ellipse(sprite, CREAM, (56, 25 + bob, 20, 10))
        pg.draw.circle(sprite, INK, (73, 27 + bob), 3)
        pg.draw.circle(sprite, INK, (63, 20 + bob), 3)
        pg.draw.circle(sprite, (255, 255, 241), (64, 19 + bob), 1)
        pg.draw.polygon(sprite, MINT, [(41, 32 + bob), (63, 35 + bob), (62, 40 + bob), (40, 37 + bob)])
        pg.draw.polygon(sprite, (76, 168, 151), [(43, 34 + bob), (23, 28 + bob), (28, 37 + bob), (41, 39 + bob)])
        step = round(math.sin(self.time * 18) * 4) if moving else 0
        pg.draw.ellipse(sprite, (96, 62, 51), (31 + step, 53, 16, 7))
        pg.draw.ellipse(sprite, (116, 73, 56), (51 - step, 53, 17, 7))
        pg.draw.ellipse(sprite, light, (49, 37 + bob, 15, 7))
        if facing < 0:
            sprite = pg.transform.flip(sprite, True, False)
        if large != 1:
            sprite = pg.transform.scale(sprite, (86 * large, 68 * large))
        self.canvas.blit(sprite, (int(x - 43 * large), int(y - 34 * large)))

    def draw_enemies(self):
        pg = self.pg
        for enemy in self.enemies:
            x, y = int(enemy['x']), int(enemy['y'])
            color = CREAM if enemy['hurt'] > 0 else (181, 99, 106)
            if enemy['kind'] == 'crawler':
                for dx in (-12, 0, 12):
                    leg = round(math.sin(self.time * 12 + dx) * 3)
                    pg.draw.line(self.canvas, (112, 73, 91), (x + dx, y + 3), (x + dx - 5, y + 15 + leg), 3)
                pg.draw.ellipse(self.canvas, color, (x - 20, y - 12, 40, 24))
                for dx in (-10, 0, 10):
                    pg.draw.polygon(self.canvas, (103, 74, 99), [(x + dx - 5, y - 7), (x + dx, y - 21), (x + dx + 5, y - 7)])
                pg.draw.circle(self.canvas, GOLD, (x + (12 if enemy['vx'] > 0 else -12), y - 2), 3)
            else:
                spread = int(12 + 7 * math.sin(self.time * 22))
                pg.draw.ellipse(self.canvas, (116, 137, 164), (x - spread - 10, y - 15, spread + 9, 27))
                pg.draw.ellipse(self.canvas, (116, 137, 164), (x + 1, y - 15, spread + 9, 27))
                pg.draw.ellipse(self.canvas, color, (x - 5, y - 13, 10, 27))
                pg.draw.circle(self.canvas, GOLD, (x, y - 10), 4)
        if self.boss:
            boss = self.boss
            x, y = int(boss['x']), int(boss['y'])
            warn = boss['mode'].startswith('warn')
            color = CREAM if boss['hurt'] > 0 else ((174, 111, 91) if boss['hp'] > 18 else (185, 79, 87))
            if warn:
                pg.draw.ellipse(self.canvas, (113, 55, 57), (x - 95, 465, 190, 14))
                self.text('!' if boss['mode'] == 'warn_charge' else 'JUMP!', x, y - 70, 22, GOLD, True)
            pg.draw.ellipse(self.canvas, (44, 28, 39), (x - 83, 470, 166, 12))
            pg.draw.ellipse(self.canvas, color, (x - 72, y, 144, 83))
            for offset in range(-55, 60, 23):
                pg.draw.polygon(self.canvas, (81, 85, 76), [(x + offset - 14, y + 15), (x + offset, y - 35 + abs(offset) // 3), (x + offset + 17, y + 15)])
                pg.draw.line(self.canvas, (137, 141, 98), (x + offset, y - 18), (x + offset + 3, y + 7), 2)
            headx = x + boss['facing'] * 57
            pg.draw.ellipse(self.canvas, (215, 181, 139), (headx - 29, y + 25, 58, 46))
            pg.draw.ellipse(self.canvas, (55, 46, 49), (headx - 18, y + 30, 36, 18))
            pg.draw.circle(self.canvas, RED if boss['hp'] <= 18 else GOLD, (headx + boss['facing'] * 12, y + 38), 5)
            for offset in (-45, 36):
                pg.draw.rect(self.canvas, (87, 57, 53), (x + offset, y + 64, 24, 23), border_radius=7)
                for k in range(3):
                    pg.draw.line(self.canvas, CREAM, (x + offset + k * 7, 475), (x + offset + k * 7 - 2, 480), 2)

    def draw_pickups(self):
        pg = self.pg
        info = self.pickup_info()
        if info and info[0] not in self.collected:
            key, x, y, *_ = info
            y += math.sin(self.time * 3) * 5
            pg.draw.circle(self.canvas, (50, 72, 77), (int(x), int(y)), 26, 1)
            pg.draw.polygon(self.canvas, GOLD, [(x, y - 15), (x + 12, y), (x, y + 15), (x - 12, y)], 2)
            label = '+' if key.startswith('heart') else ('»' if key == 'dash' else '↑')
            self.text(label, x, y - 13, 22, MINT, True)
            self.text('TOUCH TO AWAKEN', x, y - 50, 12, GOLD, True)
        if self.boss_defeated and self.room == (3, 2):
            x, y = 480, 405 + math.sin(self.time * 2) * 6
            pg.draw.circle(self.canvas, (64, 95, 78), (int(x), int(y)), 36, 1)
            pg.draw.ellipse(self.canvas, GOLD, (x - 9, y - 16, 18, 32))
            pg.draw.line(self.canvas, MINT, (x, y - 8), (x + 10, y - 28), 3)
            pg.draw.ellipse(self.canvas, MINT, (x + 4, y - 32, 16, 9))

    def draw_world(self, hud=True):
        pg = self.pg
        self.background()
        self.draw_platforms()
        self.draw_pickups()
        self.draw_enemies()
        for shot in self.projectiles:
            x, y = round(shot['x']), round(shot['y'])
            color = RED if shot['kind'] == 'root' else (194, 151, 224)
            pg.draw.circle(self.canvas, (86, 51, 82), (x, y), 12)
            pg.draw.circle(self.canvas, color, (x, y), 6)
            if shot['kind'] == 'root':
                pg.draw.line(self.canvas, GOLD, (x - 5, y + 8), (x + 4, y - 12), 3)
        pg.draw.ellipse(self.canvas, (15, 25, 30), (self.x - 6, min(self.y + 38, 473), 40, 8))
        if not self.invulnerable or int(self.time * 18) % 2:
            self.draw_weasel(self.x + 13, self.y + 16, self.facing, abs(self.vx) > 30 and self.grounded)
        if self.attack_timer > 0:
            arc = pg.Surface((W, H), pg.SRCALPHA)
            rect = self.attack_rect()
            pg.draw.arc(arc, (*CREAM, 230), rect, -1.3 if self.facing > 0 else 1.8, 1.3 if self.facing > 0 else 4.4, 5)
            self.canvas.blit(arc, (0, 0))
        for x, y, _, _, life, color in self.particles:
            pg.draw.rect(self.canvas, color, (round(x), round(y), 3 if life > .3 else 2, 3 if life > .3 else 2))
        if hud:
            self.draw_hud()
        if self.death_timer > 0:
            self.overlay(155)
            self.text('A small rest. A new beginning.', W // 2, 225, 32, CREAM, True)
            self.text('Returning to your lantern…', W // 2, 273, 18, MINT, True)

    def draw_hud(self):
        pg = self.pg
        self.panel((18, 16, 276, 75))
        for i in range(self.max_hp):
            color = RED if i < self.hp else (62, 66, 77)
            x = 35 + i * 27
            pg.draw.circle(self.canvas, color, (x + 4, 36), 5)
            pg.draw.circle(self.canvas, color, (x + 12, 36), 5)
            pg.draw.polygon(self.canvas, color, [(x - 1, 37), (x + 17, 37), (x + 8, 48)])
        self.text(f'{self.shards:03} amber   ·   CLAW  J / Z', 31, 62, 12, GOLD)
        self.text('DASH' + (' READY' if self.dash_cooldown <= 0 else ' …') if 'dash' in self.abilities else 'DASH  —', 320, 24, 12, MINT if 'dash' in self.abilities else MUTED)
        self.text('DOUBLE LEAP' if 'double_jump' in self.abilities else 'DOUBLE LEAP  —', 320, 46, 12, MINT if 'double_jump' in self.abilities else MUTED)
        self.draw_minimap()
        if self.room_title_timer > 0:
            self.text(ROOMS[self.room][0].upper(), W // 2, 110, 26, CREAM, True)
            self.text(ROOMS[self.room][2], W // 2, 146, 14, MUTED, True)
        if self.boss:
            boss = self.boss
            self.panel((270, 94, 420, 48), border=(120, 77, 75))
            self.text('THORNBACK · THE ROOTBOUND', 480, 99, 12, GOLD, True)
            pg.draw.rect(self.canvas, (57, 43, 53), (285, 121, 390, 7), border_radius=3)
            pg.draw.rect(self.canvas, RED, (285, 121, max(1, int(390 * boss['hp'] / boss['max_hp'])), 7), border_radius=3)
        if self.toast_timer > 0:
            self.panel((44, 497, W - 88, 31))
            # Long ability explanations get a smaller font to preserve the viewport.
            size = 12 if len(self.toast) > 90 else 14
            self.text(self.toast, W // 2, 503, size, GOLD, True)
        else:
            self.text('A D  MOVE    SPACE  JUMP    J  CLAW    SHIFT  DASH    E  INTERACT    M / TAB  MAP    ESC  PAUSE', W // 2, 514, 12, MUTED, True)
        if self.room in ((0, 1), (3, 1)) and abs(self.rect.centerx - 270) < 65:
            self.text('[ E ] REST', 270, 369, 12, GOLD, True)

    def draw_minimap(self):
        pg = self.pg
        self.panel((791, 16, 151, 103))
        for room in ROOMS:
            col, row = room
            rect = pg.Rect(804 + col * 31, 29 + row * 23, 26, 18)
            pg.draw.rect(self.canvas, (74, 114, 108) if room in self.visited else (30, 43, 54), rect, border_radius=2)
            if room == self.room:
                pg.draw.rect(self.canvas, GOLD, rect, 2, border_radius=2)
            if room == (3, 2) and room in self.visited:
                self.text('×' if not self.boss_defeated else '·', rect.centerx, rect.y - 2, 16, RED, True)
        self.text('M · HOLLOW MAP', 866, 101, 12, MUTED, True)

    def overlay(self, alpha=200):
        veil = self.pg.Surface((W, H), self.pg.SRCALPHA)
        veil.fill((*INK, alpha))
        self.canvas.blit(veil, (0, 0))

    def draw_map(self):
        pg = self.pg
        self.draw_world(False)
        self.overlay(238)
        self.text('THE HOLLOW', 40, 24, 32, CREAM)
        self.text(f'{len(self.visited)} / 12 chambers discovered', 42, 67, 14, MUTED)
        self.text('M / TAB / ESC · RETURN', 706, 37, 14, MINT)
        for room in ROOMS:
            col, row = room
            x, y = 44 + col * 159, 126 + row * 113
            seen = room in self.visited
            for delta in ((1, 0), (0, 1)):
                target = (col + delta[0], row + delta[1])
                if target in self.visited and seen:
                    a, b = (x + 70, y + 40), (x + 70 + delta[0] * 159, y + 40 + delta[1] * 113)
                    pg.draw.line(self.canvas, (64, 98, 104), a, b, 4)
            color = (40, 68, 73) if seen else (23, 33, 46)
            border = GOLD if room == self.room else ((91, 146, 137) if seen else (43, 52, 65))
            self.panel((x, y, 141, 83), color, border, 7)
            self.text(ROOMS[room][0] if seen else 'Uncharted', x + 70, y + 10, 12, CREAM if seen else (99, 115, 128), True)
            if seen:
                label = 'YOU' if room == self.room else ''
                if room in ((0, 1), (3, 1)):
                    label += '  LANTERN'
                if room == (1, 0):
                    label += '  DASH' + (' +' if 'dash' in self.abilities else '')
                if room == (1, 2):
                    label += '  LEAP' + (' +' if 'double_jump' in self.abilities else '')
                if room == (3, 2):
                    label += '  BOSS' if not self.boss_defeated else '  RESTORED'
                if room in ((2, 0), (2, 2)):
                    label += '  HEART'
                self.text(label.strip() or 'PASSAGE', x + 70, y + 35, 12, GOLD, True)
                if room == self.room:
                    self.text(f'{len(self.enemies)} enemies here', x + 70, y + 57, 12, MUTED, True)
        self.panel((709, 123, 211, 320))
        self.text('YOUR JOURNEY', 726, 140, 16, GOLD)
        lines = [('01  Find Wind Dash', 'dash' in self.abilities), ('02  Find Double Leap', 'double_jump' in self.abilities), ('03  Reach the Briar', (3, 2) in self.visited), ('04  Defeat Thornback', self.boss_defeated)]
        for i, (line, done) in enumerate(lines):
            self.text(line, 726, 181 + i * 43, 14, MINT if done else CREAM)
            self.text('COMPLETE' if done else 'UNDISCOVERED', 726, 201 + i * 43, 12, MUTED)
        self.text('Gold outline · your chamber', 725, 376, 12, GOLD)
        self.text('Lantern · save & restore', 725, 398, 12, MUTED)
        self.text('Arrow doors connect floors. Amber seals require an awakened ability.', 44, 490, 14, MUTED)

    def button(self, label, rect, selected=False):
        pg = self.pg
        self.panel(rect, (44, 75, 76) if selected else (25, 43, 53), MINT if selected else (66, 88, 94), 7)
        self.text(label, rect[0] + rect[2] // 2, rect[1] + 11, 18, CREAM, True)
        self.buttons.append((pg.Rect(rect), label))

    def draw_title(self):
        pg = self.pg
        self.background()
        self.draw_platforms()
        self.overlay(90)
        self.text('A SMALL HERO. A DEEPER WORLD.', 64, 67, 14, MINT)
        self.text('Briar &', 60, 102, font=self.bold)
        self.text('Burrow', 60, 163, font=self.bold, color=GOLD)
        self.text('The Hollow is losing its light.', 65, 248, 18)
        self.text('Find your claws. Chase the wind. Bring it home.', 65, 276, 16, MUTED)
        self.draw_weasel(726, 330, 1, False, 4)
        self.text('PIP · KEEPER OF THE LAST LANTERN', 731, 452, 12, GOLD, True)
        labels = ['Continue journey', 'New journey'] if self.save_path.exists() else ['Begin journey']
        for i, label in enumerate(labels):
            self.button(label, (65, 328 + i * 57, 270, 47), self.menu_selection % len(labels) == i)
        self.text('ARROWS / WASD · SELECT     ENTER · BEGIN     F11 · FULLSCREEN', 65, 472, 12, MUTED)
        self.text(self.title_hint or 'Explore 12 connected chambers · Find two abilities · Face Thornback', 65, 503, 12, RED if self.title_hint else MUTED)

    def draw_pause(self):
        self.draw_world()
        self.overlay(210)
        self.text('Take a breath, Pip.', W // 2, 106, 32, CREAM, True)
        for i, label in enumerate(['Resume', 'View map', 'Return to lantern', 'Save & title']):
            self.button(label, (340, 170 + i * 55, 280, 44), self.menu_selection % 4 == i)
        self.text('SPACE · JUMP     J / Z · CLAW     SHIFT / K / X · DASH', W // 2, 418, 14, MUTED, True)
        self.text('W / S at arrow doors · change floors     E at lantern · save', W // 2, 445, 14, MUTED, True)
        self.text('F11 · fullscreen    F10 · sound ' + ('on' if self.volume else 'off'), W // 2, 473, 12, MINT, True)

    def draw_victory(self):
        self.draw_world(False)
        self.overlay(210)
        self.text('THE HOLLOW BREATHES AGAIN', W // 2, 116, 32, GOLD, True)
        self.text('A little weasel. A very large heart.', W // 2, 175, 22, CREAM, True)
        self.text('Thornback is free of the briar. The Sunseed is safe.', W // 2, 221, 18, MUTED, True)
        self.text(f'{len(self.visited)} / 12 chambers explored   ·   {self.shards} amber gathered', W // 2, 257, 16, MINT, True)
        self.button('Keep exploring', (340, 320, 280, 48), True)
        self.text('Journey saved. Thank you for playing Briar & Burrow.', W // 2, 407, 14, MUTED, True)

    def activate(self, label):
        if label == 'Continue journey':
            self.load()
        elif label in ('New journey', 'Begin journey'):
            # A fresh run only replaces a previous save when a lantern or upgrade is reached.
            self.reset()
            self.state = 'playing'
            self.announce('Find Wind Dash above and Double Leap below. E at lanterns saves.', 7)
        elif label in ('Resume', 'Keep exploring'):
            self.state = 'playing'
        elif label == 'View map':
            self.state = 'map'
        elif label == 'Return to lantern':
            self.hp = self.max_hp
            self.enter_room(self.checkpoint, 260, 430)
            self.state = 'playing'
        elif label == 'Save & title':
            if self.save():
                self.state = 'title'
                self.menu_selection = 0

    def events(self):
        pg = self.pg
        for event in pg.event.get():
            if event.type == pg.QUIT:
                if self.state != 'title':
                    self.save()
                self.running = False
            elif event.type == pg.KEYDOWN:
                key = event.key
                if key == pg.K_F11:
                    self.fullscreen = not self.fullscreen
                    self.screen = pg.display.set_mode((0, 0), pg.FULLSCREEN) if self.fullscreen else pg.display.set_mode((1152, 648), pg.RESIZABLE)
                elif key == pg.K_F10:
                    self.volume = not self.volume
                elif self.state in ('title', 'paused', 'victory'):
                    if key in (pg.K_DOWN, pg.K_s):
                        self.menu_selection += 1
                    elif key in (pg.K_UP, pg.K_w):
                        self.menu_selection -= 1
                    elif key in (pg.K_RETURN, pg.K_SPACE):
                        labels = [label for _, label in self.buttons]
                        if labels:
                            self.activate(labels[self.menu_selection % len(labels)])
                    elif key == pg.K_ESCAPE and self.state == 'paused':
                        self.state = 'playing'
                elif self.state == 'map':
                    if key in (pg.K_m, pg.K_TAB, pg.K_ESCAPE):
                        self.state = 'playing'
                elif self.state == 'playing':
                    if key in (pg.K_m, pg.K_TAB):
                        self.state = 'map'
                    elif key == pg.K_ESCAPE:
                        self.state, self.menu_selection = 'paused', 0
                    elif self.death_timer <= 0:
                        if key in (pg.K_SPACE, pg.K_c):
                            self.jump_buffer = .12
                            self.jump()
                        elif key in (pg.K_j, pg.K_z):
                            self.attack()
                        elif key in (pg.K_LSHIFT, pg.K_RSHIFT, pg.K_k, pg.K_x):
                            self.dash()
                        elif key == pg.K_e:
                            self.interact()
                        elif key in (pg.K_w, pg.K_UP):
                            self.interact('up')
                        elif key in (pg.K_s, pg.K_DOWN):
                            self.interact('down')
            elif event.type == pg.KEYUP and event.key in (pg.K_SPACE, pg.K_c) and self.state == 'playing' and self.vy < -200:
                self.vy *= .55
            elif event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
                size = self.screen.get_size()
                scale = min(size[0] / W, size[1] / H)
                pos = ((event.pos[0] - (size[0] - W * scale) / 2) / scale, (event.pos[1] - (size[1] - H * scale) / 2) / scale)
                for rect, label in self.buttons:
                    if rect.collidepoint(pos):
                        self.activate(label)
                        break
            elif event.type == pg.WINDOWFOCUSLOST and self.state == 'playing':
                self.state = 'paused'

    def render(self):
        self.buttons = []
        if self.state == 'title':
            self.draw_title()
        elif self.state == 'paused':
            self.draw_pause()
        elif self.state == 'map':
            self.draw_map()
        elif self.state == 'victory':
            self.draw_victory()
        else:
            self.draw_world()
        width, height = self.screen.get_size()
        scale = min(width / W, height / H)
        surface = self.pg.transform.scale(self.canvas, (max(1, int(W * scale)), max(1, int(H * scale))))
        offset = (round(random.uniform(-4, 4)), round(random.uniform(-3, 3))) if self.shake > 0 and self.state == 'playing' else (0, 0)
        self.screen.fill((8, 13, 23))
        self.screen.blit(surface, ((width - surface.get_width()) // 2 + offset[0], (height - surface.get_height()) // 2 + offset[1]))
        self.pg.display.flip()

    def run(self):
        frames = 0
        self.render()
        while self.running:
            dt = min(self.clock.tick(120) / 1000, 1 / 30)
            self.events()
            if self.state == 'playing':
                keys = self.pg.key.get_pressed()
                movement = int(keys[self.pg.K_d] or keys[self.pg.K_RIGHT]) - int(keys[self.pg.K_a] or keys[self.pg.K_LEFT])
                # Fixed substeps keep dash collisions solid even on slow machines.
                steps = max(1, math.ceil(dt / (1 / 120)))
                for _ in range(steps):
                    if self.state == 'playing':
                        self.update(dt / steps, movement)
            else:
                self.time += dt
            self.render()
            frames += 1
            if self.args.frames and frames >= self.args.frames:
                break
        if self.args.screenshot:
            self.args.screenshot.parent.mkdir(parents=True, exist_ok=True)
            self.pg.image.save(self.canvas, str(self.args.screenshot))

    def smoke_test(self):
        import tempfile
        # Exercise real physics, progression, combat, boss, persistence and every UI state.
        with tempfile.TemporaryDirectory(prefix='briar-test-') as directory:
            self.save_path = Path(directory) / 'progress.json'
            self.state = 'playing'
            for _ in range(100):
                self.update(1 / 120)
            assert self.grounded and self.rect.bottom == 480, 'Landing collision failed'
            self.x = 340  # Clear the overhead ledge before testing full jump height.
            start = self.y
            assert self.jump()
            for _ in range(20):
                self.update(1 / 120)
            assert self.y < start - 40, 'Jump did not gain height'
            assert not self.transition((3, 1), 20, 430), 'Dash gate should be locked'
            self.enter_room((1, 0), 457, 250)
            self.collect()
            assert 'dash' in self.abilities and self.save_path.exists()
            assert self.dash()
            assert self.transition((3, 1), 20, 430), 'Dash gate did not unlock'
            assert not self.transition((2, 2), 20, 430), 'Leap gate should be locked'
            self.enter_room((1, 2), 457, 250)
            self.collect()
            assert 'double_jump' in self.abilities
            self.jumps, self.grounded, self.coyote = 1, False, 0
            assert self.jump() and self.jumps == 2, 'Double jump failed'
            self.enter_room((2, 0), 714, 309)
            self.collect()
            assert self.max_hp == 7, 'Heart pickup failed'
            self.enter_room((1, 1), 470, 430)
            enemy = self.enemies[0]
            enemy['x'], enemy['y'] = 530., 454.
            for _ in range(3):
                self.attack_cooldown = 0
                self.attack()
                self.update_enemies(0)
            assert len(self.enemies) == 1 and self.shards == 3, 'Claw combat failed'
            self.invulnerable = 0
            old_hp = self.hp
            self.damage()
            assert self.hp == old_hp - 1
            self.damage()
            assert self.hp == old_hp - 1, 'Invulnerability failed'
            self.invulnerable = 0
            self.damage(self.hp)
            self.update(1.6)
            assert self.room == self.checkpoint and self.hp == self.max_hp, 'Respawn failed'
            self.enter_room((3, 2), 470, 430)
            assert not self.transition((2, 2), 40, 430), 'Boss arena should seal'
            self.boss['timer'] = 0
            self.update_boss(.01)
            assert self.boss['mode'] == 'warn_charge'
            self.boss['timer'] = 0
            self.update_boss(.01)
            assert self.boss['mode'] == 'charge'
            self.boss['mode'], self.boss['timer'] = 'warn_slam', 0
            self.update_boss(.01)
            assert len(self.projectiles) == 2, 'Boss slam failed'
            self.boss['x'], self.boss['hp'] = 550., 1
            self.attack_cooldown = 0
            self.attack()
            self.update_boss(.01)
            assert self.boss_defeated and self.state == 'victory', 'Boss victory failed'
            assert self.save()
            assert self.load() and self.boss_defeated and 'dash' in self.abilities, 'Save/load failed'
            for room in ROOMS:
                self.enter_room(room, 260, 430)
                self.draw_world()
            for state in ('title', 'playing', 'paused', 'map', 'victory'):
                self.state = state
                self.render()
            self.state = 'playing'
            self.enter_room((1, 1), 420, 268)
            self.render()
            if self.args.screenshot:
                self.args.screenshot.parent.mkdir(parents=True, exist_ok=True)
                self.pg.image.save(self.canvas, str(self.args.screenshot))
                self.state = 'map'
                self.render()
                self.pg.image.save(self.canvas, str(self.args.screenshot.with_name('map.png')))
                self.boss_defeated = False
                self.enter_room((3, 2), 420, 438)
                self.state = 'playing'
                self.boss['mode'], self.boss['timer'] = 'warn_slam', .6
                self.room_title_timer = self.toast_timer = 0
                self.render()
                self.pg.image.save(self.canvas, str(self.args.screenshot.with_name('boss.png')))
        print('PASS: landing, jumping, ability gates, upgrades, double jump, combat, invulnerability, respawn, boss attacks/victory, save/load, all 12 rooms and all UI states.')


if __name__ == '__main__':
    main()
