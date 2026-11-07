# Briar & Burrow

A small, complete Pygame metroidvania. Play as **Pip**, a scarf-wearing weasel, and reclaim the Sunseed from Thornback, the Rootbound. All artwork and sound effects are generated in code; no asset downloads or accounts are required.

## Play on Windows

Double-click **Start.bat**. The launcher finds Python 3.10 or newer, creates a local `.venv`, installs Pygame on the first launch, and opens the game. Internet is needed only to install Pygame. If Python is missing, install it from https://www.python.org/downloads/windows/ with the Python launcher enabled.

Manual setup from this folder:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

## Controls

| Action | Keys |
| --- | --- |
| Move | A / D or Left / Right |
| Jump; jump again after Double Leap | Space or C |
| Claw attack | J or Z |
| Wind Dash after collecting it | Shift, K, or X |
| Ascend / descend at arrow doors | W / S or Up / Down |
| Interact; use a door; rest at a lantern | E |
| World map, goals, discovered rooms | M or Tab |
| Pause; return from map | Escape |
| Fullscreen | F11 |
| Sound on / off | F10 |
| Menu selection | W / S or arrows, Enter; or mouse click |

Release jump early for a shorter hop. Dash grants a brief invulnerability window. Land to recharge an aerial dash. Claw repeatedly, jump over ground shockwaves, and watch the boss's warning before a charge. The boss becomes faster below half health.

## Your journey

- Explore **12 connected chambers** across the canopy, burrows and briarworks. Walk off left/right edges to change chambers; use arrow doors to travel between floors.
- Search **Wind Shrine** above Hearthburrow for Wind Dash. Search **Old Burrows** below for Double Leap. Amber seals indicate a missing ability.
- Touch the floating ability crystals and heart upgrades to collect them. Two hearts raise maximum health from six to eight.
- Fight thorn crawlers and spore moths. Collect amber by defeating enemies; every nine amber from ordinary enemies restores one health pip.
- Rest at Hearthburrow or Last Lantern with E to fully heal and set your checkpoint. Death returns you there without removing upgrades.
- Face **Thornback** in the bottom-right chamber. Both abilities are needed to reach the arena. After victory you can keep exploring.

Progress is stored locally in `saves/progress.json`. Upgrades, lanterns, victory, Save & title, and closing an active game save your discoveries. Continue starts at the last lantern with full health; individual enemy positions are reset. Starting a new journey replaces the previous save when that run next saves. Pausing also offers a return to the lantern if you get stuck. The map pauses gameplay.

## Developer checks

```powershell
.\.venv\Scripts\python.exe main.py --smoke-test --screenshot screenshots/gameplay.png
.\.venv\Scripts\python.exe main.py --headless --frames 120 --screenshot screenshots/title.png
```

The smoke test uses a temporary save directory and checks real movement/collision, ability locks, pickups, combat, invulnerability, respawn, boss attacks and victory, persistence, every room, and every interface state. `--save-dir PATH` selects another save directory. The window is resizable with a fixed 16:9 playfield and letterboxing. No cloud services, telemetry or external assets are used.
