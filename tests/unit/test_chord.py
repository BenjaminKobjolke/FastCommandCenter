"""Characterization tests for chord normalization and settings persistence."""

from command_palette import MemoryStore

from config.settings_store import DEFAULT_CHORD, SettingsStore, normalize_chord


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
