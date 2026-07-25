# Tray menu

FastCommandCenter has no main window — the system tray icon and its
right-click menu are the only always-visible surface of the app. Everything
lives in `gui/tray.py`, wired up once from `fastcommandcenter.py:main()`.

## Where it's built

`build_tray(app, open_palette, open_shortcuts_config)` (`gui/tray.py`) creates:

- **Icon** — `app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)`,
  a built-in Qt icon (no custom asset yet).
- **`FastCommandTrayIcon`** — a small `QSystemTrayIcon` subclass. It exists only
  to hold `menu_ref: QMenu | None` — see "Lifetime" below.
- **Context menu** (`QMenu`) — four entries, in order:
  1. `Open palette` → `open_palette` (same callback the global hotkey triggers)
  2. `Configure keyboard shortcuts` → `open_shortcuts_config` (opens the
     palette navigated straight into the shared `python-command-palette`
     shortcut editor — drilled into the same window, not a separate dialog)
  3. *(separator)*
  4. `Quit` → `app.quit`

`main()` calls `build_tray(app, open_palette, open_shortcuts_config)` after the
hotkey manager is started, and does **not** need to keep the returned value —
the tray keeps itself alive (below).

## Lifetime — why the tray is app-parented

`QSystemTrayIcon(icon, app)` passes `app` as the Qt parent. Without a parent
(and without a Python variable holding a reference), the tray icon would be
garbage-collected the moment `build_tray()` returns, and the icon silently
disappears — no error, no crash, it just never shows.

`QSystemTrayIcon.setContextMenu()` does **not** take ownership of the `QMenu`
the way most Qt parent/child widgets do, so the menu needs its own keep-alive:
`FastCommandTrayIcon.menu_ref` holds it for the tray's lifetime.

## Behavior notes

- `app.setQuitOnLastWindowClosed(False)` (`fastcommandcenter.py`) is required
  because this is a background app: closing the shortcut editor is "the last
  window" from Qt's point of view, and without this flag the whole app would
  exit when it closes.
- The tray's `Open palette` entry and the global OS hotkey both call the same
  `open_palette()` closure in `fastcommandcenter.py` — there's exactly one
  code path that opens the palette.
