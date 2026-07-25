"""Persists the OS-global hotkeys and the palette's appearance, using the
command-palette library's own `Store` (JSON file under
`%APPDATA%\\FastCommandCenter\\command-palette\\state.json` in production;
`MemoryStore` in tests).

Per-command hotkeys live in the palette library's own `key_bindings` key via
`KeymapState` (shared `Store`, see `fastcommandcenter.py`); `global_hotkey`
below is the pre-multi-hotkey key, kept only for `migrate_legacy_chord`'s
one-time seed of a pre-existing local install. Appearance is stored under its
own `appearance` key.
"""

from __future__ import annotations

from dataclasses import asdict

from command_palette import DefaultPair, JsonStore, KeymapState, PaletteConfig, Store
from command_palette.store import default_state_path

APP_NAME = "FastCommandCenter"
CHORD_KEY = "global_hotkey"
DEFAULT_CHORD = "ctrl+alt+space"
APPEARANCE_KEY = "appearance"
OPEN_PALETTE_COMMAND_ID = "open_palette"
DEFAULT_BINDINGS: list[DefaultPair] = [("Ctrl+Alt+Space", OPEN_PALETTE_COMMAND_ID)]

# Fields the settings dialog lets the user tune; open_chord is palette-internal
# and frameless is fixed by this app, so both are excluded from persistence.
_APPEARANCE_FIELDS = (
    "width_pct",
    "height_pct",
    "font_pt",
    "opacity_pct",
    "active_fg",
    "inactive_fg",
)


def normalize_chord(qt_chord: str) -> str:
    """Convert a Qt chord string (e.g. "Ctrl+Alt+P") to the lowercase, "+"-joined
    format winhotkeys expects ("ctrl+alt+p"; "meta" -> "win")."""
    parts = [part.strip().lower() for part in qt_chord.split("+") if part.strip()]
    parts = ["win" if part == "meta" else part for part in parts]
    return "+".join(parts)


def _to_qt_chord(winhotkeys_chord: str) -> str:
    """The inverse of `normalize_chord`: winhotkeys format ("ctrl+alt+p") ->
    Qt chord format ("Ctrl+Alt+P"; "win" -> "Meta")."""
    parts = [part.strip() for part in winhotkeys_chord.split("+") if part.strip()]
    parts = ["Meta" if part == "win" else part.capitalize() for part in parts]
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

    def migrate_legacy_chord(self, keymap_state: KeymapState) -> None:
        """One-time: seed `open_palette`'s chord from the pre-multi-hotkey
        `global_hotkey` key, so an existing local install doesn't silently lose
        a chord the user already customized. No-op once the user has touched
        `open_palette` through the new per-command editor (its chords differ
        from `DEFAULT_BINDINGS`' untouched default), or if nothing -- or still
        the default -- was ever saved under the legacy key.
        """
        default_chords = tuple(
            chord for chord, command_id in DEFAULT_BINDINGS if command_id == OPEN_PALETTE_COMMAND_ID
        )
        if keymap_state.effective().chords_for(OPEN_PALETTE_COMMAND_ID) != default_chords:
            return
        if not self.has_chord():
            return
        chord = self.get_chord()
        if chord == DEFAULT_CHORD:
            return
        # Replace, not add: an untouched default chord must not survive
        # alongside the migrated one (that would register two global hotkeys
        # for the same command).
        keymap_state.remove_command(OPEN_PALETTE_COMMAND_ID)
        keymap_state.assign(_to_qt_chord(chord), OPEN_PALETTE_COMMAND_ID)

    def get_appearance(self) -> PaletteConfig:
        """The saved palette appearance, or library defaults if none was ever saved.

        This app's palette is always frameless, regardless of what was stored.
        """
        data = self._store.read(APPEARANCE_KEY) or {}
        overrides = {key: value for key, value in data.items() if key in _APPEARANCE_FIELDS}
        return PaletteConfig(frameless=True, **overrides)

    def set_appearance(self, config: PaletteConfig) -> None:
        """Persist the tunable appearance fields of ``config``."""
        data = asdict(config)
        self._store.write(APPEARANCE_KEY, {key: data[key] for key in _APPEARANCE_FIELDS})
