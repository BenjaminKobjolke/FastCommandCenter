# Command palette

The command palette is FastCommandCenter's only UI — there is no main window.
A system-wide global hotkey (default `Ctrl+Alt+Space`, rebindable) opens it;
the tray icon (`docs/TRAY_MENU.md`) is the only other entry point. The dialog
itself, its appearance/QSS, drill-in navigation, and shortcut editor all come
from the `python-command-palette` library
(`D:\GIT\BenjaminKobjolke\python-command-palette`) — this doc covers how this
app *uses* that library. For the library's own reference, see its
`docs/NAVIGATION.md` and `docs/APPEARANCE.md`.

## Opening it

`fastcommandcenter.py`'s `open_palette()` calls `palette.open()`. The global
hotkey (`core/hotkey_manager.py` + `core/hotkey_bridge.py`) and the tray's
`Open palette` action both call this same closure — one code path.

## The command list

Built once by `build_commands()` in `palette/commands.py`:

| Command | Behavior |
|---|---|
| `open_palette` | The opener itself — also a bindable hotkey target, like every other command. |
| `settings` (title: "Configure keyboard shortcuts") | Navigable — drills into the shortcut editor in the same window. |
| `Appearance: font size` / `window width` / `window height` / `opacity` | Navigable — drills into a value list. |
| `Appearance: selected row color` / `other rows color` | Navigable — drills into "Choose custom color…" / "Reset to theme default". |
| `Tools: manage folders` | Navigable — add/remove the folders scanned for external tools (see "External tool commands" below). |
| `quit` (title: "Quit FastCommandCenter") | Terminal — runs and closes the palette. |

Every command is a bindable global-hotkey target (see `Configure keyboard
shortcuts` below) — there's no separate "the" hotkey; each command can hold
multiple chords.

## In-palette navigation

A **navigable** command (`Command.submenu` or `Command.on_navigate` set)
doesn't close the dialog when chosen — it drills into a value list *inside
the same window*, Esc backs out one level at a time. This app never opens a
second window for any of it.

Two behaviors the library handles automatically for every drill-in:

- **Returns to where you were.** Picking a value (or backing out with Esc)
  restores the row you had highlighted before drilling in — choosing
  `Appearance: font size`, picking a size, and landing back on the root list
  re-highlights `Appearance: font size`, not the top of the list.
- **Opens on the active value.** Each Appearance value list marks the row
  matching the setting currently in effect (`ListEntry(selected=True)`) —
  entering `Appearance: font size` with `font_pt=18` highlights "18 pt", not
  the first row.

## Appearance is a set of palette commands

Every tunable (font size, window width/height %, opacity, row colors) is
configured **through the palette itself**, one `Appearance: …` command per
setting — never a separate settings dialog. Picking a value:

1. Persists it via `settings_store.set_appearance()`.
2. Applies it live via `apply_appearance()` (`fastcommandcenter.py`) — calls
   both `palette.set_config()` (affects the *next* `open()`) and
   `palette.restyle_open_dialog()` (re-styles the dialog that's open *right
   now*), so the change is visible immediately without closing and reopening.

## External tool commands

Beyond the fixed list above, the palette carries one **dynamic** command per
action declared by an external FastTools app — e.g. "Fast Keyboard Mouse:
Toggle mouse mode" (`command_id` = `tool.fastkeyboardmouse.toggle`). Firing
one finds-or-launches the tool and sends it the action over `WM_COPYDATA`;
the tool runs in a "palette-managed" mode where it does *not* register its
own OS-global hotkey, since this palette is meant to be the single hotkey
authority — run the same tool directly (not through the palette) and it
behaves exactly as it always has.

`Tools: manage folders` is how you add or remove which folders get scanned
for these — "Add folder…" opens a native folder picker (the same "one
unavoidable exception to staying inside the palette" the color pickers use),
each configured folder shows as a `Remove: <path>` row. A newly added tool's
actions become visible the next time the palette is *opened*, and start with
no hotkey bound — bind one through `Configure keyboard shortcuts` below, same
as any other command.

See **`docs/EXTERNAL_TOOLS.md`** for how this is implemented (the
`fasttool_host` bridge, the in-place command-list refresh, the repo split)
and `FastCommandCenter-tool-bridge/CONTRACT.md` for the wire protocol.

## Configure keyboard shortcuts

`settings` mounts the library's in-palette shortcut editor
(`open_shortcut_editor_in_palette`) onto the already-open dialog — command
list → inline "press a shortcut" capture → reassign/add-vs-replace/clear
confirms, all as pushed levels of the same window. Edits apply live via
`core/hotkey_manager.py`'s `apply()`, which re-registers every OS-global
hotkey in one shot.

`settings` also has a plain `run` (`open_shortcuts_config`): a global hotkey
bound directly to it fires with no palette open yet, so `run` opens the
palette navigated straight to the editor (`palette.open(navigate_to="settings")`)
— `on_navigate` alone needs a live dialog to push into.

See `docs/SETTINGS_STORAGE.md` for the persisted shape.
