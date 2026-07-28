# How pasting works

When a text-provider result is chosen (e.g. from cli-favorites' "Favorite
Folders" or FastTextSuggester), FCC inserts the tool's resolved `text` into
the application the user was working in *before* the palette appeared. This
doc traces that mechanism end to end. The wire side (how the text got here)
is `docs/EXTERNAL_TOOLS.md` + the bridge repo's `CONTRACT.md`; this doc is
only about what happens after a result is picked.

## The paste target is captured at palette open

`fastcommandcenter.py`'s `_open_palette()` snapshots
`win32gui.GetForegroundWindow()` into `palette_target_hwnd` *before* the
dialog opens — that HWND is the window that loses focus to the palette and
is therefore the paste destination. Both entry paths run through this same
closure, so both preserve the target:

- open palette → navigate to a provider (`on_navigate`), or
- fire a global shortcut bound to a provider command (`run` →
  `_open_palette(navigate_to=command_id)`).

An asynchronous activation (`activate_text_provider`, e.g. after
FastTextSuggester's OCR) reuses the last captured `palette_target_hwnd`, and
only falls back to the *current* foreground window when no palette was open
before.

## The paste sequence

Choosing a row (`core/tool_text_provider.py`'s `_choose`):

1. Echo the pick back to the tool (`ToolBridge.notify_text_selection`, the
   v3 `selected` message — see `docs/EXTERNAL_TOOLS.md`).
2. Accept (close) the palette dialog.
3. `QTimer.singleShot(100, ...)` → `paste_to_palette_target(text)`. The
   100 ms delay lets the dialog actually dismiss and Windows finish its
   focus transition first; pasting synchronously would race the closing
   modal for the foreground.

`paste_to_palette_target` looks up the target app's paste chord
(`SettingsStore.paste_chord_for()`, see "Per-app paste chords" below) and
calls `core/text_paste.py`'s
`paste_text(text, palette_target_hwnd, chord)`:

1. **Clipboard**: `QApplication.clipboard().setText(text)` followed by
   `pythoncom.OleFlushClipboard()` — the text is on the clipboard from here
   on, regardless of whether the `Ctrl+V` below lands (so a failed paste
   still leaves the value one manual `Ctrl+V` away). The flush matters: Qt
   puts a delayed-rendered data object on the OLE clipboard whose content is
   fetched via a callback into FCC's GUI thread — which the inter-chord
   `time.sleep` below blocks, making the target resolve the *previous*
   clipboard value. Flushing renders the text into the clipboard up front so
   no callback is needed. Empty text is a no-op: nothing is copied, nothing
   pasted.
2. **Refocus**: `force_foreground(target_hwnd)`
   (`core/window_activation.py`) — a background tray process is never
   Windows' foreground process, so a bare `SetForegroundWindow` would be
   blocked by the foreground lock. `force_foreground` attaches this
   process's input thread to the current foreground window's thread
   (`AttachThreadInput`), sets the target foreground, then detaches.
   Skipped when the captured HWND is 0 (nothing usable was focused).
3. **Settle**: a 300 ms pause (`_PRE_PASTE_DELAY_S`) before the first
   keystroke — without it the target can process the paste chord before
   the clipboard update has settled and paste the *previous* value
   (empirically: 100 ms too short for WezTerm, 300 ms reliable).
4. **Synthesize the paste chord**: `win32api.keybd_event` presses the
   chord's keys in order and releases them in reverse (Ctrl down, V down,
   V up, Ctrl up for the default) into whatever now owns focus — i.e. the
   restored target window, which interprets it as a normal paste. The
   chord is `Ctrl+V` unless the target's exe has an entry in the
   per-app override map (below); chord tokens resolve to virtual-key
   codes via `winhotkeys.keycodes.vk_key_names`, and an unparseable
   stored chord falls back to `Ctrl+V` rather than pasting nothing.

## Per-app paste chords (WezTerm etc.)

Some applications don't paste on `Ctrl+V` — terminals like WezTerm use
`Ctrl+Shift+V`. `SettingsStore.get_paste_overrides()`
(`config/settings_store.py`, key `paste_overrides`, see
`docs/SETTINGS_STORAGE.md`) maps a target exe basename (lowercase, e.g.
`wezterm-gui.exe`) to what to synthesize instead; unlisted apps get
`Ctrl+V`. `wezterm-gui.exe` → `ctrl+shift+v` is seeded by default.

The value can also be a comma-separated *sequence* of chords — e.g.
`ctrl+shift+v,enter` pastes and then presses Enter (paste-and-submit).
Chords are synthesized in order, each fully pressed and released, with a
300 ms pause (`_INTER_CHORD_DELAY_S`) before every follow-up chord so the
target app finishes handling the paste before e.g. the Enter arrives. A
bad token anywhere discards the whole sequence for plain `Ctrl+V` — a
partial run (paste chord dropped but a trailing Enter still fired) would
be worse than a wrong paste chord.

`fastcommandcenter.py`'s `paste_to_palette_target` resolves
`palette_target_hwnd` to its exe via `core/window_process.py`'s
`exe_basename_for_hwnd()` (pywin32; returns `None` — and thus the default
chord — for hwnd 0 or a process it may not open) and passes the looked-up
chord to `paste_text`.

Configured in-palette via **`Paste: behaviour for current application`**
(`palette/commands.py`, id `paste_behaviour`): the rows show the paste
target's exe with its current value preselected — `Ctrl+V (default)`,
`Ctrl+Shift+V`, or either followed by `, then Enter` — and picking one
persists it (picking the default removes the map entry). "Current
application" is the same `palette_target_hwnd` snapshot the paste itself
uses, so to configure any app: focus it, open the palette, pick the
command. The command is also a
bindable hotkey target; bound directly, its `run` opens the palette
navigated to the chord list, with the app that was focused at fire time as
the subject. Other chords or sequences (e.g. `shift+insert`,
`ctrl+shift+v,enter,enter`) work but must be hand-edited into
`state.json`'s `paste_overrides` map.

## Consequences and limits

- **The clipboard is overwritten.** Whatever the user had on it is replaced
  by the picked text; there is no save/restore of prior clipboard content.
- **The chord is a keystroke, not an API paste.** The target application
  must interpret the synthesized chord as paste. An app whose paste chord
  isn't `Ctrl+V` needs a `paste_overrides` entry (see "Per-app paste
  chords" above); an elevated (admin) window won't accept input from a
  non-elevated process at all — either way the text is still on the
  clipboard as the fallback.
- **The target is a snapshot.** If the user switches windows while the
  palette is open (possible via mouse — the palette is modal but other apps
  remain clickable), the paste still goes to the window captured at open
  time, not wherever focus wandered.
- **FCC owns all of this.** Per the bridge contract, the tool only supplies
  the resolved `text`; focus restoration, clipboard assignment, and the
  paste keystrokes are FCC's job — the per-app chord is FCC configuration,
  not something a tool can request, and there is currently no copy-only
  mode (a provider cannot opt out of the paste).

## Files

| File | Role |
|---|---|
| `fastcommandcenter.py` (`_open_palette`, `paste_to_palette_target`) | Captures the target HWND, resolves its per-app chord, binds both to the paste call |
| `core/text_paste.py` | Clipboard set + refocus + synthesized paste chord |
| `core/window_process.py` | `exe_basename_for_hwnd()` — keys the per-app override lookup |
| `core/window_activation.py` | `force_foreground()` — beats the foreground lock via `AttachThreadInput` |
| `core/tool_text_provider.py` (`_choose`) | Selection echo, dialog close, 100 ms delayed paste |
