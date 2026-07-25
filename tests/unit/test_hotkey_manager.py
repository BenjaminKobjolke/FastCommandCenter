"""Pure-function tests for mapping a KeyMap onto winhotkeys registrations.

``HotkeyManager.apply()`` itself needs a live Windows message pump (via
``winhotkeys``) and isn't exercised here -- this pins the pure translation
step it depends on, kept separate so it's testable without win32.
"""

from command_palette.keymap import KeyMap

from core.hotkey_manager import winhotkeys_bindings


def test_winhotkeys_bindings_normalizes_qt_chords():
    keymap = KeyMap(bindings=(("Ctrl+Alt+Space", "open_palette"), ("Ctrl+Alt+Q", "quit")))
    assert winhotkeys_bindings(keymap) == [
        ("ctrl+alt+space", "open_palette"),
        ("ctrl+alt+q", "quit"),
    ]


def test_winhotkeys_bindings_maps_meta_to_win():
    keymap = KeyMap(bindings=(("Meta+Space", "open_palette"),))
    assert winhotkeys_bindings(keymap) == [("win+space", "open_palette")]


def test_winhotkeys_bindings_empty_keymap():
    assert winhotkeys_bindings(KeyMap(bindings=())) == []
