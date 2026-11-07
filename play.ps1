$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$gamePython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
try {
    if (-not (Test-Path -LiteralPath $gamePython)) {
        $candidates = @()
        $bundledPython = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
        if (Test-Path -LiteralPath $bundledPython) {
            $candidates += @{ File = $bundledPython; Arguments = @() }
        }
        if (Get-Command py.exe -ErrorAction SilentlyContinue) {
            $candidates += @{ File = 'py.exe'; Arguments = @('-3') }
        }
        if (Get-Command python.exe -ErrorAction SilentlyContinue) {
            $candidates += @{ File = 'python.exe'; Arguments = @() }
        }
        $chosen = $null
        foreach ($candidate in $candidates) {
            $prefix = $candidate.Arguments
            $supported = $false
            try {
                & $candidate.File @prefix -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' 2>$null
                $supported = $LASTEXITCODE -eq 0
            } catch { $supported = $false }
            if ($supported) { $chosen = $candidate; break }
        }
        if (-not $chosen) {
            throw 'Python 3.10 or newer is required. Install Python from https://www.python.org/downloads/windows/ (enable the Python launcher), then open Start.bat again.'
        }
        Write-Host 'Setting up the game environment...'
        $prefix = $chosen.Arguments
        & $chosen.File @prefix -m venv (Join-Path $PSScriptRoot '.venv')
        if ($LASTEXITCODE -ne 0) {
            if (-not (Test-Path -LiteralPath $gamePython)) { throw 'Could not create the Python environment.' }
            & $gamePython -m ensurepip --upgrade --default-pip
            if ($LASTEXITCODE -ne 0) { throw 'Could not install pip into the game environment.' }
        }
    }
    $pipReady = $false
    try {
        & $gamePython -m pip --version 2>$null | Out-Null
        $pipReady = $LASTEXITCODE -eq 0
    } catch { $pipReady = $false }
    if (-not $pipReady) {
        & $gamePython -m ensurepip --upgrade --default-pip
        if ($LASTEXITCODE -ne 0) { throw 'Could not repair pip in the game environment.' }
    }
    $pygameReady = $false
    try {
        & $gamePython -c 'import pygame; assert pygame.version.vernum >= (2, 5, 7)' 2>$null | Out-Null
        $pygameReady = $LASTEXITCODE -eq 0
    } catch { $pygameReady = $false }
    if (-not $pygameReady) {
        Write-Host 'Installing Pygame (internet access is needed on the first launch)...'
        & $gamePython -m pip install --disable-pip-version-check -r (Join-Path $PSScriptRoot 'requirements.txt')
        if ($LASTEXITCODE -ne 0) { throw 'Pygame installation failed. Check your internet connection and try again.' }
    }
    & $gamePython (Join-Path $PSScriptRoot 'main.py') @args
    if ($LASTEXITCODE -ne 0) { throw 'The game exited with an error. The details are shown above.' }
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
