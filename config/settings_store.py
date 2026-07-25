"""Persists the OS-global hotkey chord, using the command-palette library's own
`Store` (JSON file under `%APPDATA%\\FastCommandCenter\\command-palette\\state.json`
in production; `MemoryStore` in tests). Stored under its own key (`global_hotkey`),
separate from the palette's internal `history`/`key_bindings` keys.
"""

from __future__ import annotations

from command_palette import JsonStore, Store
from command_palette.store import default_state_path

APP_NAME = "FastCommandCenter"
CHORD_KEY = "global_hotkey"
DEFAULT_CHORD = "ctrl+alt+space"


def normalize_chord(qt_chord: str) -> str:
    """Convert a Qt chord string (e.g. "Ctrl+Alt+P") to the lowercase, "+"-joined
    format winhotkeys expects ("ctrl+alt+p"; "meta" -> "win")."""
    parts = [part.strip().lower() for part in qt_chord.split("+") if part.strip()]
    parts = ["win" if part == "meta" else part for part in parts]
    return "+".join(parts)


class SettingsStore:
    """Reads/writes the global hotkey chord."""

    def __init__(self, store: Store | None = None) -> None:
        self._store = store or JsonStore(default_state_path(APP_NAME))

    def get_chord(self) -> str:
        """The saved chord, or the default if none was ever saved."""
        data = self._store.read(CHORD_KEY)
        if data is None:
            return DEFAULT_CHORD
        chord = data.get("chord")
        return chord if isinstance(chord, str) and chord else DEFAULT_CHORD

    def set_chord(self, chord: str) -> None:
        """Persist a new chord."""
        self._store.write(CHORD_KEY, {"chord": chord})

    def has_chord(self) -> bool:
        """Whether a chord was ever explicitly saved (vs. still on the default)."""
        return self._store.read(CHORD_KEY) is not None
