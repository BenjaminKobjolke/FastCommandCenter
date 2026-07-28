"""Unit tests for the paste sequence -> virtual-key mapping in core/text_paste.py."""

from unittest.mock import MagicMock

import win32con
from PySide6.QtGui import QClipboard

import core.text_paste as text_paste
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


def _patched_paste(monkeypatch):
    """Patch paste_text's side effects, recording call order."""
    order = []
    clipboard = MagicMock(spec=QClipboard)
    clipboard.setText.side_effect = lambda text: order.append(("set", text))
    qapp = MagicMock()
    qapp.clipboard.return_value = clipboard
    monkeypatch.setattr(text_paste, "QApplication", qapp)
    monkeypatch.setattr(text_paste.pythoncom, "OleFlushClipboard", lambda: order.append(("flush",)))
    monkeypatch.setattr(text_paste, "force_foreground", MagicMock())
    monkeypatch.setattr(text_paste.win32api, "keybd_event", lambda *args: order.append(("key",)))
    monkeypatch.setattr(text_paste.time, "sleep", MagicMock())
    return order


def test_clipboard_set_and_flushed_before_any_keystroke(monkeypatch):
    # The flush must precede the synthesized chords: the target app reads the
    # clipboard while our GUI thread is blocked in the inter-chord sleep, so
    # delayed-rendered (unflushed) data would resolve to the previous value.
    order = _patched_paste(monkeypatch)
    text_paste.paste_text("hello", 123, "ctrl+shift+v,enter")
    assert order[0] == ("set", "hello")
    assert order[1] == ("flush",)
    assert order[2:] and all(event == ("key",) for event in order[2:])


def test_empty_text_touches_neither_clipboard_nor_keyboard(monkeypatch):
    order = _patched_paste(monkeypatch)
    text_paste.paste_text("", 123)
    assert order == []
