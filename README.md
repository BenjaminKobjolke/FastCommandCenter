# FastCommandCenter

A background Windows app with no main window. Press a global keyboard shortcut
from anywhere and a command palette opens; run a command; the palette closes.
v1 lets you configure that global shortcut. Reachable via a system tray icon
or via the palette's own "Settings"/"Quit" entries.

## Install / Setup

```bash
install.bat
```

This runs `uv sync --group dev`. Requires [uv](https://docs.astral.sh/uv/) and
a git-accessible checkout of `winhotkeys` (installed automatically as a git
dependency) plus a local checkout of `python-command-palette` at
`D:\GIT\BenjaminKobjolke\python-command-palette` (installed editable).

## Usage

```bash
start.bat
```

Runs the app in the background (no console window, via `pythonw`). A tray
icon appears. Press the configured shortcut (default `Ctrl+Alt+Space`) to
open the command palette from any application. Use the palette's or tray's
**Settings** entry to rebind the shortcut; **Quit** to exit.

On first run (no shortcut saved yet), Settings opens automatically so you can
pick one.

## Dependencies

- Python `>=3.11,<3.13`
- [PySide6](https://pypi.org/project/PySide6/) `>=6.11.1` — GUI toolkit
- [command-palette](https://github.com/BenjaminKobjolke/python-command-palette) — the palette widget (editable local install)
- [winhotkeys](https://github.com/BenjaminKobjolke/winhotkeys) — OS-level global hotkey registration
- pywin32 — required by winhotkeys and the single-instance guard

## Development

```bash
uv sync --group dev
tools\run_tests.bat
uv run ruff check
uv run ruff format --check
uv run mypy
```
