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

Because this app is never Windows' foreground process and the library's
dialog does no activation of its own, `open_palette()` also schedules
`core/window_activation.py`'s `force_foreground()` (via `QTimer.singleShot`)
right before `palette.open()`, so a hotkey fired from cold start still brings
the dialog to the front — not just the tray path, which was already
foreground. `open_shortcuts_config()` does the same.

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

### External tool settings

Beyond its actions, each configured tool also carries one navigable
`<name>: settings` command — e.g. "Fast Keyboard Mouse: settings"
(`command_id` = `tool.fastkeyboardmouse.settings`). Picking it drills into
that tool's **own** settings — its internal keyboard shortcuts, tunables,
colors, flags — the same in-palette way `Appearance: …` drills into a value
list. This is not this palette's own appearance or hotkeys; it's whatever the
tool itself declares. The row list opens on "Loading settings…" while the
tool is asked over IPC, then fills in with one row per setting
(`"<label>: <current value>"`); picking a row opens the editor for that
setting's type:

- A **shortcut** setting opens the same inline "press a shortcut" capture
  `Configure keyboard shortcuts` uses.
- **int**, **bool**, and **enum** settings drill into a value list, exactly
  like an `Appearance: …` command.
- A **color** setting opens the native color wheel (the same "one
  unavoidable exception to staying inside the palette" the folder/color
  pickers use).

Picking a value sends it to the tool, which persists it and reloads whatever
depends on it *itself* — **this app never reads or writes the tool's config
file**, only the typed value crosses the wire. The row list refreshes to the
tool's actual post-apply state once it replies, so a value the tool clamped
or rejected shows correctly rather than trusting what was picked. If a
configured tool doesn't support this (an older version, or a tool with
nothing to expose), the list shows "Tool didn't respond — is it running?"
rather than hanging or erroring — its actions still work normally either way.
FastTool-only settings, such as `Hide tray icon in Command Center mode`, are
still owned by the tool; they are simply ignored or treated differently when
the same executable is run standalone instead of through `--palette`.

See **`docs/EXTERNAL_TOOLS.md`** for how this is implemented (the
`fasttool_host` bridge, the in-place command-list refresh, the settings
protocol, the repo split) and `FastCommandCenter-tool-bridge/CONTRACT.md` for
the wire protocol.

## External text providers

An external tool may declare a live text provider. Its manifest label becomes
a navigable command; selecting it keeps the FCC dialog open and sends the
typed filter text to the tool. FCC displays only the newest correlated reply;
while a reply is in flight the previous results stay visible, so typing never
blanks the list (the "Loading suggestions..." row only shows before the first
reply).
Choosing a result closes FCC, restores the application that was active before
the palette opened, copies the tool's resolved text to the clipboard, and
pastes it with `Ctrl+V`.
The chosen result is also echoed back to the tool (fire-and-forget `selected`
message), so a tool can bump its own usage/frecency ranking — cli-favorites'
"Favorite Folders" does.

A global shortcut bound to a text-provider command opens FCC directly at
that provider. The window focused before the shortcut fired remains the
paste target.

These are separate command paths: selection calls `on_navigate` on the live
dialog, while a global shortcut calls `run` with no dialog available. A text
provider is not complete unless both paths open the same provider level.

FastTextSuggester uses this flow for words, lines, replacements, multiline
blocks, CSV/TSV values, and recent OCR. Its capture actions are separate root
commands; successful OCR asks FCC to reopen directly in the suggestion level.
cli-favorites uses it for "Favorite Folders" (pick a favorite → its resolved
path is pasted) and consumes the `selected` echo to bump the same frecency
counts its CLI writes.

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

The Windows key is a supported modifier — bind it like any other
(`config/settings_store.py`'s `normalize_chord()`/`_to_qt_chord()` convert
Qt's `Meta` token to/from winhotkeys' `win`, and `core/hotkey_manager.py`
registers it with `MOD_WIN`). Capturing it in "Press a shortcut…" relies on
the library's Windows-only low-level keyboard hook
(`python-command-palette`'s `command_palette/win_capture.py`), since a plain
Qt window never sees a Win+key press otherwise — the shell reserves it first.
OS-secured combos (Ctrl+Alt+Del, the Secure Attention Sequence) can't be
captured or bound by any user-mode app, this one included.

See `docs/SETTINGS_STORAGE.md` for the persisted shape.
