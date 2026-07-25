# Settings dialog

`gui/settings_dialog.py` — `SettingsDialog`. Only setting exposed today: the
OS-global hotkey chord that opens the command palette.

## How it opens

`open_settings()` (defined inline in `fastcommandcenter.py:main()`) creates a
`SettingsDialog(settings_store, hotkey_manager)` and calls `.exec()` — modal.
Two call sites reach it:

- **First run**: `main()` calls it automatically when
  `settings_store.has_chord()` is `False` (no chord ever saved).
- **Any time after**: tray menu "Settings" entry, or the palette's own
  `Settings: configure global shortcut` command
  (`palette/commands.py` → `build_commands()`).

Both pass the same `open_settings` closure, so there is one code path.

## Layout

- Label: "Global shortcut to open the command palette:"
- `QKeySequenceEdit`, pre-filled with the current chord (converted from
  storage format to Qt display format — see below)
- `QDialogButtonBox` with **Save** / **Cancel**

## Save flow

`_save()`:

1. Reads the `QKeySequence` typed into the edit box.
2. If non-empty, converts it to storage format via
   `normalize_chord()` (`config/settings_store.py`) and:
   - `store.set_chord(chord)` — persists it (see `docs/SETTINGS_STORAGE.md`)
   - `hotkey_manager.update_hotkey(chord)` — re-registers the OS-level hotkey
     immediately, no restart needed
3. Calls `self.accept()` either way (an empty chord just closes the dialog
   without changing anything).

Cancel wires straight to `self.reject()` — no persistence, no hotkey change.

## Chord format conversion

Two representations, converted at the dialog boundary:

| Format | Example | Used by |
|---|---|---|
| Qt display | `"Ctrl+Alt+P"` | `QKeySequenceEdit` widget |
| storage/winhotkeys | `"ctrl+alt+p"` | `SettingsStore`, `HotkeyManager` (OS `RegisterHotKey`) |

- `_to_qt_chord()` (`settings_dialog.py`) — storage → Qt, for pre-filling the
  widget on open. `"win"` → `"Meta"`.
- `normalize_chord()` (`settings_store.py`) — Qt → storage, on save.
  `"Meta"` → `"win"`.

Both are pure string transforms, no shared state; either can be called
independently (e.g. tests exercise `normalize_chord()` alone).
