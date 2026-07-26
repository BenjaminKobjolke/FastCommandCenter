"""Characterization tests for chord normalization and settings persistence."""

from command_palette import KeymapState, MemoryStore, PaletteConfig

from config.settings_store import (
    DEFAULT_BINDINGS,
    DEFAULT_CHORD,
    SettingsStore,
    _to_qt_chord,
    normalize_chord,
)


def test_normalize_chord_lowercases_and_joins():
    assert normalize_chord("Ctrl+Alt+P") == "ctrl+alt+p"


def test_normalize_chord_maps_meta_to_win():
    assert normalize_chord("Meta+Space") == "win+space"


def test_settings_store_defaults_when_nothing_saved():
    store = SettingsStore(MemoryStore())
    assert store.get_chord() == DEFAULT_CHORD
    assert store.has_chord() is False


def test_settings_store_round_trip():
    store = SettingsStore(MemoryStore())
    store.set_chord("ctrl+alt+space")
    assert store.get_chord() == "ctrl+alt+space"
    assert store.has_chord() is True


def test_settings_store_appearance_defaults_when_nothing_saved():
    store = SettingsStore(MemoryStore())
    appearance = store.get_appearance()
    assert appearance == PaletteConfig(frameless=True)


def test_settings_store_appearance_round_trip():
    store = SettingsStore(MemoryStore())
    saved = PaletteConfig(
        width_pct=50,
        height_pct=40,
        font_pt=14,
        opacity_pct=80,
        active_fg="#ffffff",
        inactive_fg="#888888",
    )
    store.set_appearance(saved)
    loaded = store.get_appearance()
    assert loaded == PaletteConfig(
        frameless=True,
        width_pct=50,
        height_pct=40,
        font_pt=14,
        opacity_pct=80,
        active_fg="#ffffff",
        inactive_fg="#888888",
    )


def test_settings_store_appearance_ignores_open_chord_and_frameless_from_config():
    store = SettingsStore(MemoryStore())
    store.set_appearance(PaletteConfig(open_chord="Ctrl+Alt+X", frameless=False))
    assert store.get_appearance() == PaletteConfig(frameless=True)


def test_to_qt_chord_titlecases_and_joins():
    assert _to_qt_chord("ctrl+alt+p") == "Ctrl+Alt+P"


def test_to_qt_chord_maps_win_to_meta():
    assert _to_qt_chord("win+space") == "Meta+Space"


def test_normalize_chord_and_to_qt_chord_round_trip():
    assert _to_qt_chord(normalize_chord("Ctrl+Alt+P")) == "Ctrl+Alt+P"


def test_migrate_legacy_chord_seeds_open_palette_from_saved_chord():
    store = MemoryStore()
    settings = SettingsStore(store)
    settings.set_chord("ctrl+alt+p")
    keymap_state = KeymapState(store, DEFAULT_BINDINGS)

    settings.migrate_legacy_chord(keymap_state)

    assert keymap_state.effective().chords_for("open_palette") == ("Ctrl+Alt+P",)


def test_migrate_legacy_chord_noop_when_nothing_ever_saved():
    store = MemoryStore()
    settings = SettingsStore(store)
    keymap_state = KeymapState(store, DEFAULT_BINDINGS)

    settings.migrate_legacy_chord(keymap_state)

    assert keymap_state.effective().chords_for("open_palette") == ("Ctrl+Alt+Space",)


def test_migrate_legacy_chord_noop_when_saved_chord_is_already_the_default():
    store = MemoryStore()
    settings = SettingsStore(store)
    settings.set_chord(DEFAULT_CHORD)
    keymap_state = KeymapState(store, DEFAULT_BINDINGS)

    settings.migrate_legacy_chord(keymap_state)

    assert keymap_state.effective().chords_for("open_palette") == ("Ctrl+Alt+Space",)


def test_settings_store_tool_dirs_defaults_to_empty():
    store = SettingsStore(MemoryStore())
    assert store.get_tool_dirs() == []


def test_settings_store_tool_dirs_round_trip():
    store = SettingsStore(MemoryStore())
    store.set_tool_dirs(["D:/GIT/BenjaminKobjolke/FastTools/FastKeyboardMouse"])
    assert store.get_tool_dirs() == ["D:/GIT/BenjaminKobjolke/FastTools/FastKeyboardMouse"]


def test_migrate_legacy_chord_noop_when_open_palette_already_customized():
    store = MemoryStore()
    settings = SettingsStore(store)
    settings.set_chord("ctrl+alt+p")
    keymap_state = KeymapState(store, DEFAULT_BINDINGS)
    # Mirrors what the shortcut editor's "Replace" path does: remove the
    # default chord(s) first, then assign the new one -- not a bare `assign`,
    # which would only append alongside the still-live default binding.
    keymap_state.remove_command("open_palette")
    keymap_state.assign("Ctrl+Alt+Z", "open_palette")

    settings.migrate_legacy_chord(keymap_state)

    assert keymap_state.effective().chords_for("open_palette") == ("Ctrl+Alt+Z",)
