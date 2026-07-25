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
  "global_hotkey": { "chord": "ctrl+alt+space" },
  "history": { ... },
  "key_bindings": { ... }
}
```

- **`global_hotkey`** — owned by FastCommandCenter (`config/settings_store.py`,
  `CHORD_KEY = "global_hotkey"`). The only key this app writes.
- **`history`**, **`key_bindings`** — owned internally by the
  `python-command-palette` library (recently-used commands, any user-rebound
  command shortcuts). FastCommandCenter never reads or writes these directly;
  they exist because `CommandPalette` shares the same `JsonStore` instance
  by default (same `default_state_path()` call, same app name).

Keeping the hotkey under its own key, separate from the library's keys, means
either side can add/change its own data without colliding with the other's.

## Read/write path

`SettingsStore` (`config/settings_store.py`) is the only code in this app that
touches the file, via `Store.read()` / `Store.write()`:

- `get_chord()` → `store.read("global_hotkey")` → `DEFAULT_CHORD`
  (`"ctrl+alt+space"`) if the key is absent or malformed.
- `set_chord(chord)` → `store.write("global_hotkey", {"chord": chord})`.
- `has_chord()` → `store.read("global_hotkey") is not None` — used once, at
  startup, to decide whether to auto-open Settings on first run
  (`fastcommandcenter.py`).

## Failure behavior

`JsonStore._load()` (library code) never raises: a missing file returns `{}`,
and a missing/corrupt file logs a warning and is treated as empty rather than
crashing the app. A bad or hand-edited `state.json` degrades to "no chord
saved yet" — the app falls back to `DEFAULT_CHORD` and offers Settings again,
it doesn't fail to start.

## Testing

`SettingsStore(store=...)` takes an optional `Store`; tests pass
`MemoryStore()` (in-process dict, same `Store` protocol) instead of a real
`JsonStore` — no filesystem, no `%APPDATA%` involved.
