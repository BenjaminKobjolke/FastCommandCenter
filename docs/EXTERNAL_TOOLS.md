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

## Making a tool FCC-compatible

Use `D:\GIT\BenjaminKobjolke\FastTools\FastCommandCenter-tool-bridge\CONTRACT.md`
as the source of truth for the wire format and manifest schema. From a tool
repo, the practical checklist is:

1. Vendor or depend on the bridge client shim for the tool's runtime
   (`FastCommandCenter-tool-bridge/client/...`; AHK tools usually vendor the
   AHK shim into `lib/`).
2. Add a `fasttool.json` next to the tool executable. It must declare the
   stable tool id, display name, IPC window title, launch executable, launch
   args including `--palette`, and one action id/label per command FCC should
   expose.
3. In the tool startup, parse `--palette` through the client shim before
   registering global hotkeys. Palette mode must create the IPC window and
   skip the tool's own OS-global hotkey registration; standalone mode keeps
   the original behavior.
4. Map each `fasttool.json` action id to the tool's internal command label or
   handler so FCC can send `WM_COPYDATA` action messages.
5. If the tool installs active-mode keyboard hooks or wildcard hotkeys, apply
   the bridge's yielded host chords while the tool is active so FCC's own
   hotkeys keep working.
6. Optionally expose the tool's own settings through the settings protocol.
   The tool remains the owner of its INI/config persistence and reload/apply
   behavior; FCC only displays typed values and sends selected updates.
7. If the tool suggests text, declare a `text_providers` entry and register
   its query callback through the client shim. Provider commands are
   bindable, so FCC must support both command entry paths described below.
8. For compiled tools, rebuild the executable after source changes. FCC
   launches the `fasttool.json` executable, not the source file.
9. In FCC, add the tool folder through `Tools: manage folders`, then bind the
   generated action or text-provider commands through `Configure keyboard
   shortcuts`.
10. Verify every exposed workflow from both the open palette and its assigned
    global shortcut. For a text provider, also select a result and confirm it
    pastes into the window focused before FCC opened.

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
- **Text-provider commands have two independent FCC entry paths.** Selecting
  one inside an open palette calls `Command.on_navigate(dialog)`, which pushes
  the provider onto that dialog. A global hotkey never calls
  `on_navigate`; it dispatches `Command.run()`, which must open FCC with
  `palette.open(navigate_to=command_id)`. Implementing only `on_navigate`
  makes palette selection work while every assigned shortcut silently does
  nothing. Keep the unit test in `tests/unit/test_tool_commands.py` that calls
  the generated provider command's `run()` and asserts its command id was
  passed to FCC's provider opener.
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

**A tool's `fasttool.json` `launch.exe` names a compiled binary, not its
source.** `ToolBridge` only ever launches that exe — it never touches the
tool's `.ahk`/source files. After editing a tool's source (e.g.
FastKeyboardMouse's `.ahk` files), rebuild it with the tool's own build
script (`tools\build.bat` in FastKeyboardMouse) before testing through FCC,
or the exe silently keeps its old behavior. This is easy to misdiagnose: the
stale exe still launches fine (tray icon and all) via `find_window`/`_launch`
— only its *behavior* is stale — so it looks like the source change had no
effect rather than "forgot to rebuild."

## Keeping this app's global hotkeys working while a tool is active

`core/tool_commands.py`'s `build_tool_commands()` takes an optional
`yield_chords` callable; `fastcommandcenter.py` passes it a closure
(`yield_chords()`) that reads `winhotkeys_bindings(keymap_state.effective())`
fresh on every call. Every `bridge.fire(...)` call carries the current set of
neutral-format chords this app has registered — not just the one that fired —
so a tool being driven by one chord (e.g. a toggle) also learns about every
other chord this app owns.

This exists because this app's hotkeys use Win32 `RegisterHotKey`, which sits
*after* a low-level keyboard hook in Windows' input chain. A tool that
installs its own hook while active (FastKeyboardMouse's AutoHotkey `*`-
wildcard hotkeys, which match a key regardless of held modifiers) can swallow
a chord this app owns before `RegisterHotKey` ever sees it — e.g. `Alt+Q`
bound to FastKeyboardMouse's own toggle got eaten by its `*q` (center cursor)
binding once active, so the toggle could only be fired again from the palette
itself. See `FastCommandCenter-tool-bridge/CONTRACT.md`'s "Yielding hotkeys
while a tool is active" for the wire format and what a tool does with it.

## Settings protocol (v2): editing a tool's own settings

Beyond firing actions, the palette can also edit a tool's **own** settings —
its internal shortcuts, tunables, colors, flags (e.g. FastKeyboardMouse's
`FastKeyboardMouse.ini`) — through `<name>: settings`, a navigable command
built alongside the action commands. The defining constraint, and why this
needed a real protocol addition rather than just another action: **this app
never reads or writes a tool's config file.** The tool remains the sole
owner of how its settings are persisted and applied; this app only ever sees
typed values over IPC. Full wire format: `FastCommandCenter-tool-bridge/CONTRACT.md`'s
"Settings protocol (v2)" section.

- **Reply channel.** Action-fire (v1) is one-way, host → tool. Settings needs
  a reply — a tool's current values, and confirmation after a change — so
  `fasttool_host.receiver.SettingsReceiver` runs a second hidden window,
  `FastToolIPC::host`, symmetric with a tool's own `FastToolIPC::<id>`
  window. A tool's client shim resolves it via `FindWindow` and sends its
  `snapshot` there, the same primitive and direction the host already uses
  to reach a tool, just reversed. `ToolBridge` owns one `SettingsReceiver`
  instance (created alongside its process-tracking dict, torn down in
  `shutdown()`) and re-exposes its decoded replies as `settings_received`, a
  Qt signal — a tool's reply arrives asynchronously, on `SettingsReceiver`'s
  own background thread, and crosses to the GUI thread via a queued
  connection the same way `core/hotkey_bridge.py` already does for winhotkeys.
- **`ToolBridge.describe_settings(tool_id)`** / **`ToolBridge.set_setting(tool_id, setting_id, value)`**
  (`fasttool_host.bridge`) are the send side — find-or-launch the tool (same
  as `fire()`), then send a `describe` or `set` message. Both are
  fire-and-forget; the reply is whatever the next matching `settings_received`
  signal carries, not a return value.
- **`ToolBridge.manifests`** exposes every loaded `ToolManifest`, not just the
  derived `ToolAction`s `load()` returns — `core/tool_commands.py` needs a
  tool's id *and* name to build its `<name>: settings` command, and reusing
  this typed model beats re-deriving them by parsing `ToolAction.title`.
- **`core/tool_commands.py`**'s `build_tool_commands()` now returns one
  additional navigable `Command` per manifest (`command_id` =
  `tool.<id>.settings`, `on_navigate` set, `run` a no-op — same
  drill-in-only shape as `Appearance: …`/`manage_tool_folders`, not the
  direct-hotkey-when-closed special case `settings` has). It's still filtered
  by `refresh_tool_commands()`'s existing `command_id.startswith("tool.")`
  check without any changes there — the settings command's id shares that
  prefix.
- **`core/tool_settings_editor.py`** is the actual editor: a class holding
  the live `FilterListDialog` + tool identity + the `ToolBridge`, modeled on
  `python-command-palette`'s own `_LevelShortcutEditor`
  (`shortcut_editor_inline.py`) — same "list → type-appropriate editor" shape,
  reusing the same `push_level`/`push_capture_level`/`refresh_current_level`
  primitives. Differs from the shortcut editor in one structural way: every
  step there is synchronous (a `KeymapState` edit finishes before the next
  line runs), but a settings `describe`/`set` reply arrives *later*, over
  IPC — so `_ToolSettingsEditor` connects to `bridge.settings_received` fresh
  per outstanding request and disconnects as soon as it's used, rather than
  holding one connection for the editor's whole lifetime. A 3-second timeout
  degrades to a "Tool didn't respond" row if no reply ever arrives (an older
  tool, or one simply not running).
- **Per-type editors**, all reusing existing library primitives — no new UI
  code in `python-command-palette` itself: `shortcut` → the same inline
  chord-capture overlay `Configure keyboard shortcuts` uses;
  `int`/`bool`/`enum` → a pushed value-list level, same shape as
  `Appearance: …`; `color` → the native `QColorDialog`, the same "one
  unavoidable exception to staying inside the palette" the appearance color
  pickers already use. Picking a value-list entry `pop_level()`s back to the
  settings list *before* calling `set_setting` — the eventual snapshot reply
  refreshes "the current level", so it must already be back on the settings
  list by the time that reply arrives, not still on the value-list level that
  was only ever meant to be transient.
- **A tool's client shim** (`FastCommandCenter-tool-bridge/client/…`)
  implements the tool half: answering `describe` with a `snapshot`, applying
  a `set` (persist + reload + re-snapshot). FastKeyboardMouse's is
  `lib/PaletteSettings.ahk` — one `FastToolPalette_AddSetting(...)` call per
  exposed setting, binding a generic per-type getter/setter to that setting's
  global variable name (AHK v1 has no closures; `Func(...).Bind(varName)`
  stands in for one). Neutral chord ↔ AHK hotkey-syntax translation
  (`FastToolPalette_NeutralToNative`/`NativeToNeutral`, `FastToolPalette.ahk`)
  reuses the same neutral format `yield_chords` already established.

### FastTool-only settings

Some tool settings are meaningful only when the executable is launched by
FastCommandCenter with `--palette`. The current convention is that these stay
tool-owned, live in the tool's own INI under `[FastTool]`, and are exposed
through the same settings protocol as any other tool setting. For example,
FastKeyboardMouse and FastWindowLayout both expose `HideTrayIcon` as
`Hide tray icon in Command Center mode`: palette-managed launches hide or
show their own tray icon from that value, while standalone launches keep the
normal tray icon behavior. The host does not special-case these settings or
write the INI; it only displays the bool row and sends the selected value.

## Debugging the settings protocol

Two tools, for the two sides of the wire, born from actually chasing "Tool
didn't respond" bugs — both real, both silent (no exception the palette
could show, no window that failed to open):

- **`tools/diag_settings.py`** (this repo) — exercises `ToolBridge.describe_settings()`
  against a real tool directly, bypassing the palette UI entirely:

  ```
  uv run python tools/diag_settings.py "D:\path\to\ToolFolder"
  ```

  Prints each stage (receiver window creation, manifest load, `describe`
  sent, snapshot received or not) and exits non-zero on the first failure.
  Its main value: telling apart "the wire protocol itself is broken" from
  "something in the palette's UI wiring is broken" — if this script gets a
  snapshot but the palette still shows "Tool didn't respond", the bug is in
  `core/tool_settings_editor.py`/`core/tool_commands.py`, not the protocol.
  Run with the tool **not** already running (it launches one, same as the
  palette would) and rerun after any rebuild — a stale already-running
  instance answers with whatever code it had loaded at launch, not what's on
  disk now.

- **`palette_debug.log`** — an AHK-side debug log, written next to a tool's
  exe by `FastToolPalette_DebugLog()` (`FastToolPalette.ahk`,
  `FastCommandCenter-tool-bridge/client/ahk` is the source of truth, vendor
  the copy into the tool's `lib/` the same as the rest of that file). One
  line per stage of the round trip: `OnCopyData` (the raw `dwData`/`cbData`
  received), `HandleSettingsMessage` (the parsed `kind`), `SendSnapshot`
  (how many settings, JSON length), `SendToHost` (whether the host's
  `FastToolIPC::host` window was found, and the raw `SendMessageW` result).
  A caught exception inside the tool's own getter/setter code logs too,
  labeled with the AHK line number. Always-on, not gated behind a flag —
  this protocol crosses two processes and a Win32 IPC boundary, exactly
  where a MsgBox can't help. Delete the file yourself if it grows large;
  there's no rotation.

Two real, non-obvious bugs got found this way (both in the generic
`FastToolPalette.ahk` shim, so any AHK-based tool using it was affected):

1. `DllCall("FindWindow", "Str", "", "Str", "FastToolIPC::host", "Ptr")` —
   `"Str", ""` is an **empty string** for the class-name parameter, not
   NULL. No window has an empty class name, so this silently always
   returned 0. Fix: `"Ptr", 0` for a true NULL.
2. Even with a correct hwnd in hand, the `SendMessage` **command** (as
   opposed to a raw `DllCall`) re-resolves its `WinTitle` target
   (`ahk_id %hostHwnd%`) through AHK's own window-matching engine — which
   respects `DetectHiddenWindows` (off by default). The host's reply window
   is hidden (same as every `FastToolIPC::*` window in this whole system),
   so the command silently failed to target it even with the right hwnd.
   Fix: `DllCall("SendMessageW", "Ptr", hostHwnd, ...)` directly — bypasses
   AHK's window-matching entirely, mirrors exactly how the host's own
   `fasttool_host.copydata.send_action`/`send_settings` already send (raw
   `SendMessageW` against an hwnd, no title matching).

Both were invisible from the palette (just an eventual "Tool didn't
respond") and invisible to `diag_settings.py` alone (it only proves *this
side's* window exists and a message was sent, not that the *other* side's
send actually landed) — the AHK-side log was what pinned down exactly which
DllCall was failing and why.

## Orphaned hotkeys

Removing a tool folder while one of its actions still has a hotkey bound
leaves an orphaned `command_id` in the keymap. Firing it becomes a harmless
no-op (`dispatch.get(command_id, lambda: None)()`) — the same graceful-orphan
behavior the shortcut editor already has for a manually cleared binding.
Nothing cleans up the orphaned keymap entry automatically.

## Text provider protocol (v3)

Text providers are dynamic, navigable tool commands rather than fixed actions.
`fasttool_host.ToolBridge.query_text()` sends the provider/session/request/query
tuple and emits typed `ToolTextResults` replies. FCC's adapter rejects stale
request ids and maps the newest rows into a pushed palette provider. The tool
owns matching and returns resolved insertion text; FCC owns focus restoration,
clipboard assignment, and `Ctrl+V`.

Tools may emit `text_provider_activation_requested`, allowing an asynchronous
workflow such as OCR to reopen FCC directly at a declared provider. The bridge
contract and Python client implementation live in the sibling bridge repo;
the nested-provider UI primitive lives in `python-command-palette`; only their
composition belongs in FCC.

External settings also support `string` (inline palette text entry) and
`directory` (native directory picker) in addition to the v2 setting types.

### Text-provider verification matrix

Before considering a new provider integrated, verify all of these paths:

| Entry path | Expected behavior |
|---|---|
| Select provider in an open palette | Pushes the provider level and accepts typed queries |
| Fire its assigned global shortcut | Opens FCC directly at the provider level |
| Choose a result from either path | Closes FCC and pastes into the previously focused window |
| Query while the tool is not running | FCC launches it and displays its first correlated reply |
| Query while the tool is already running | FCC reuses it and displays the newest correlated reply |
| Tool requests activation asynchronously | FCC waits for any active modal to close, then opens the provider |

The first two rows are intentionally separate tests: palette selection uses
`on_navigate`, while shortcut dispatch uses `run`.

## Repo split: where does a change belong?

Same judgment call as the `python-command-palette` dependency (see the top
of `CLAUDE.md`):

- **`FastCommandCenter-tool-bridge`** — the wire protocol itself
  (`CONTRACT.md`, both action-fire and the settings protocol), the AHK/Python
  client shims other tools vendor/depend on, `fasttool_host`'s manifest
  parsing, `ToolBridge` (find-or-launch, `WM_COPYDATA` send/receive,
  `QProcess` lifecycle, `describe_settings`/`set_setting`/`settings_received`),
  the `SettingsReceiver`/`FastToolIPC::host` window, the `ToolSetting`/
  `ToolSettings` models — anything usable by another PySide6 host or another
  tool, not specific to FastCommandCenter's own command list.
- **This repo** — `core/tool_commands.py`, `core/tool_settings_editor.py`,
  the `manage_tool_folders` command, `SettingsStore.get_tool_dirs()`/
  `set_tool_dirs()`, anything that calls into `fasttool_host`'s public API
  rather than living inside it.
- **A tool's own repo** (e.g. `FastKeyboardMouse`) — which of its settings it
  declares editable, how it persists them (its own ini/config format,
  entirely its call), and what "reload" means for it.

If it's ambiguous, ask before implementing rather than guessing.

## See also

- `docs/COMMAND_PALETTE.md`'s "External tool commands" and "External tool
  settings" sections — the user-facing behavior (what shows up in the
  palette, how binding and settings-editing work).
- `docs/SETTINGS_STORAGE.md` — the `tool_dirs` persisted shape.
- `FastCommandCenter-tool-bridge/CONTRACT.md` — the wire protocol, including
  "Settings protocol (v2)".
