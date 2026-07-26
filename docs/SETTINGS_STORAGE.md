# Settings storage (JSON)

## File location

```
%APPDATA%\FastCommandCenter\command-palette\state.json
```

Computed by `command_palette.store.default_state_path("FastCommandCenter")`
(`python-command-palette/command_palette/store.py`). On non-Windows it'd fall
back to `$XDG_CONFIG_HOME` or `~/.config`, but this app only ships for Windows.

## Format: one JSON object, multiple keys

The whole file is a single `{key: value, ...}` object. `JsonStore.write()`
round-trips the entire file on every write (load → mutate one key → dump) —
fine at this scale, a handful of small keys.

```json
{
  "appearance": { ... },
  "global_hotkey": { "chord": "ctrl+alt+space" },
  "history": { ... },
  "key_bindings": { "overrides": [{ "chord": "Ctrl+Alt+Q", "command_id": "quit" }] },
  "tool_dirs": { "dirs": ["D:\\GIT\\BenjaminKobjolke\\FastTools\\FastKeyboardMouse"] }
}
```

- **`appearance`** — owned by FastCommandCenter (`config/settings_store.py`,
  `APPEARANCE_KEY = "appearance"`). Font size, window width/height %, opacity,
  selected/other row colors.
- **`tool_dirs`** — owned by FastCommandCenter (`config/settings_store.py`,
  `TOOL_DIRS_KEY = "tool_dirs"`). The list of folders scanned for a
  `fasttool.json` manifest — one entry per external FastTools app the palette
  can launch and drive (see `docs/COMMAND_PALETTE.md`'s "External tool
  commands" and `FastCommandCenter-tool-bridge/CONTRACT.md`). Empty by
  default; never hand-edit this — use the palette's own "Tools: manage
  folders" command (`get_tool_dirs()`/`set_tool_dirs()` are the only reader/
  writer, both in `config/settings_store.py`).
- **`key_bindings`** — owned by the `python-command-palette` library
  (`KeymapState`, `KEY_BINDINGS_KEY = "key_bindings"`) but this is the key that
  actually matters now: every command's global hotkey(s) live here as
  chord-keyed overrides layered onto `SettingsStore.DEFAULT_BINDINGS`. Both
  `fastcommandcenter.py`'s `KeymapState` and `CommandPalette`'s own (unused,
  since this app never calls `install_shortcut`) history/keymap state share the
  same `JsonStore` instance, so this key is the single source of truth for
  what fires which command.
- **`global_hotkey`** — **legacy**, from the pre-multi-hotkey single-chord
  design. Nothing writes it anymore (`gui/settings_dialog.py`, its only writer,
  is deleted). It's read exactly once, by `SettingsStore.migrate_legacy_chord()`
  at startup, to seed `open_palette`'s chord into `key_bindings` for an
  existing local install that had customized it — see "Migration" below.
- **`history`** — owned internally by the library (recently-used commands, for
  the palette's own MRU ordering). FastCommandCenter never reads or writes it.

## Migration off the single-hotkey key

`SettingsStore.migrate_legacy_chord(keymap_state)` (`config/settings_store.py`,
called once at startup in `fastcommandcenter.py`) is a one-time bridge:

1. No-op if `open_palette`'s effective chords already differ from
   `DEFAULT_BINDINGS`' untouched default (the user has already used the new
   per-command shortcut editor, or a previous run already migrated).
2. No-op if `global_hotkey` was never saved, or was saved as exactly the
   default chord (nothing to preserve).
3. Otherwise: `keymap_state.remove_command("open_palette")` (clears the
   still-live default chord) then `keymap_state.assign(...)` the legacy chord
   — **replace**, not add, so the user doesn't end up with two live global
   hotkeys for the same command.

After this runs once, `key_bindings` is authoritative and `global_hotkey` goes
permanently dormant (still present on disk for old installs, never read again
outside this function).

## Read/write path

- `SettingsStore` (`config/settings_store.py`) owns `appearance` and the
  legacy `global_hotkey` key, via `Store.read()` / `Store.write()`.
- `KeymapState` (library) owns `key_bindings` — `fastcommandcenter.py`
  constructs one directly (`KeymapState(shared_store, DEFAULT_BINDINGS)`) and
  passes it to `open_shortcut_editor` and `HotkeyManager.apply()`.

`SettingsStore.get_chord()`/`set_chord()`/`has_chord()` still exist (the
legacy key's accessors) but only `migrate_legacy_chord()` calls them now — no
other code path writes `global_hotkey`.

## Failure behavior

`JsonStore._load()` (library code) never raises: a missing file returns `{}`,
and a missing/corrupt file logs a warning and is treated as empty rather than
crashing the app. A bad or hand-edited `state.json` degrades to "no bindings
saved yet" — the app falls back to `DEFAULT_BINDINGS` and offers the shortcut
editor again on next launch, it doesn't fail to start.

## Testing

`SettingsStore(store=...)` and `KeymapState(store, defaults)` both take a
`Store`; tests pass a shared `MemoryStore()` (in-process dict, same `Store`
protocol) instead of a real `JsonStore` — no filesystem, no `%APPDATA%`
involved. See `tests/unit/test_chord.py` for the migration's characterization
tests.
