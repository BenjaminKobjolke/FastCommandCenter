# External tool integration

FastCommandCenter can act as the single global-hotkey authority and launcher
for other FastTools apps (FastKeyboardMouse today; more AHK/Python tools
later), instead of each app registering its own OS hotkey. This doc covers
how that works *from this repo's side*. For the wire protocol itself — the
`WM_COPYDATA` message format, window-title discovery, the `fasttool.json`
manifest shape — see the dedicated sibling repo's `CONTRACT.md`:
`D:\GIT\BenjaminKobjolke\FastTools\FastCommandCenter-tool-bridge\CONTRACT.md`.
That repo also ships the AHK/Python client shims a tool vendors/depends on to
speak the protocol, and the `fasttool_host` Python package this app depends
on to speak the host side of it.

## Why a tool defers its own hotkey

Windows `RegisterHotKey` is exclusive per chord — two processes can't both
own the same key combo. So an external tool that wants its hotkey configured
*through this palette*, not its own settings UI, must not register its own
OS-global hotkey when launched by it; instead the palette owns the chord and
sends the tool an action id when it fires. Each tool implements this as a
two-mode contract via a client shim from `FastCommandCenter-tool-bridge`:
`--palette` on the command line selects palette-managed mode (no own
hotkey, waits for an action over `WM_COPYDATA`); no flag = the tool's
original, fully standalone behavior — nothing changes there. Run the same
tool directly and it behaves exactly as it always has.

## How it plugs into this app

- **`SettingsStore.get_tool_dirs()` / `set_tool_dirs()`** (`config/settings_store.py`)
  persist the list of folders scanned for a `fasttool.json` manifest, under
  the `tool_dirs` key — see `docs/SETTINGS_STORAGE.md`. Never hand-edit this;
  it's set through the palette (below).
- **`core/tool_commands.py`**'s `build_tool_commands(settings_store, bridge=None)`
  loads every `fasttool.json` under those folders (via
  `fasttool_host.ToolBridge`) and returns one ordinary `Command` per declared
  action — `run` calls `bridge.fire(tool_id, action_id)`, which finds-or-
  launches the tool and sends it the action. These commands are
  indistinguishable from a built-in one to the rest of this app: bindable in
  the shortcut editor, fireable by hotkey or from the palette, dispatched the
  same way. The function accepts an existing `ToolBridge` so a reload doesn't
  orphan a bridge's already-tracked launched-process state.
- **`Tools: manage folders`** (`palette/commands.py`, navigable) is how a
  folder gets added (native folder picker) or removed (select its "Remove:
  `<path>`" row). Either path calls `fastcommandcenter.py`'s
  `refresh_tool_commands()`.
- **`refresh_tool_commands()`** (`fastcommandcenter.py`) rebuilds the tool
  commands and mutates the running `commands` list and hotkey `dispatch` dict
  **in place** — `commands[:] = ...`, `dispatch.clear()` + `.update(...)`,
  never `commands = ...`. This matters: the palette itself, the shortcut
  editor's closure, and the hotkey-dispatch closure all captured a reference
  to the *original* list/dict at startup — reassigning the name would make
  them diverge (they'd keep pointing at the stale object). In-place mutation
  is required so all three see the update without a restart or being touched
  themselves. A newly added tool's commands become visible the next time the
  palette is *opened* (there's no live row-refresh of an already-open
  drilled-in list — unlike `Appearance: …`'s live restyle via
  `restyle_open_dialog()`, that would need a `python-command-palette` change,
  out of scope for now).
- **`tool_bridge.shutdown()`** is wired to `app.aboutToQuit` — terminates any
  tool instances the bridge itself launched. A tool already running when the
  palette fires an action (found via `FindWindow`, not launched by this
  bridge) is left alone.

## Orphaned hotkeys

Removing a tool folder while one of its actions still has a hotkey bound
leaves an orphaned `command_id` in the keymap. Firing it becomes a harmless
no-op (`dispatch.get(command_id, lambda: None)()`) — the same graceful-orphan
behavior the shortcut editor already has for a manually cleared binding.
Nothing cleans up the orphaned keymap entry automatically.

## Repo split: where does a change belong?

Same judgment call as the `python-command-palette` dependency (see the top
of `CLAUDE.md`):

- **`FastCommandCenter-tool-bridge`** — the wire protocol itself
  (`CONTRACT.md`), the AHK/Python client shims other tools vendor/depend on,
  `fasttool_host`'s manifest parsing and `ToolBridge` (find-or-launch,
  `WM_COPYDATA` send/receive, `QProcess` lifecycle) — anything usable by
  another PySide6 host or another tool, not specific to FastCommandCenter's
  own command list.
- **This repo** — `core/tool_commands.py`, the `manage_tool_folders` command,
  `SettingsStore.get_tool_dirs()`/`set_tool_dirs()`, anything that calls into
  `fasttool_host`'s public API rather than living inside it.

If it's ambiguous, ask before implementing rather than guessing.

## See also

- `docs/COMMAND_PALETTE.md`'s "External tool commands" section — the
  user-facing behavior (what shows up in the palette, how binding works).
- `docs/SETTINGS_STORAGE.md` — the `tool_dirs` persisted shape.
- `FastCommandCenter-tool-bridge/CONTRACT.md` — the wire protocol.
