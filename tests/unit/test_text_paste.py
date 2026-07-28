"""Unit tests for the paste sequence -> virtual-key mapping in core/text_paste.py."""

import win32con

from core.text_paste import _sequence_vks

_CTRL_V = [win32con.VK_CONTROL, ord("V")]


def test_single_ctrl_v_chord():
    assert _sequence_vks("ctrl+v") == [_CTRL_V]


def test_single_ctrl_shift_v_chord():
    assert _sequence_vks("ctrl+shift+v") == [[win32con.VK_CONTROL, win32con.VK_SHIFT, ord("V")]]


def test_shift_insert_chord():
    assert _sequence_vks("shift+insert") == [[win32con.VK_SHIFT, win32con.VK_INSERT]]


def test_sequence_of_paste_then_enter():
    assert _sequence_vks("ctrl+shift+v,enter") == [
        [win32con.VK_CONTROL, win32con.VK_SHIFT, ord("V")],
        [win32con.VK_RETURN],
    ]


def test_unknown_token_falls_back_to_plain_ctrl_v():
    assert _sequence_vks("hyper+v") == [_CTRL_V]


def test_bad_token_in_any_chord_discards_the_whole_sequence():
    # Partial execution (paste failed but Enter fires) would be worse than a
    # plain Ctrl+V -- the fallback replaces the entire sequence.
    assert _sequence_vks("ctrl+shift+v,bogus") == [_CTRL_V]
    assert _sequence_vks("bogus,enter") == [_CTRL_V]


def test_empty_sequence_falls_back_to_plain_ctrl_v():
    assert _sequence_vks("") == [_CTRL_V]
