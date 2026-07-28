"""Paste text into the window that owned focus before FCC opened."""

from __future__ import annotations

import time

import pythoncom
import win32api
import win32con
from PySide6.QtWidgets import QApplication
from winhotkeys.keycodes import vk_key_names

from config.settings_store import DEFAULT_PASTE_CHORD
from core.window_activation import force_foreground

_FALLBACK_VKS = [vk_key_names[token] for token in DEFAULT_PASTE_CHORD.split("+")]

# Pause before each follow-up chord in a sequence (e.g. the Enter in
# "ctrl+shift+v,enter") -- gives the target app time to finish handling the
# paste before the next keystroke arrives.
_INTER_CHORD_DELAY_S = 0.3

# Pause between clipboard set/refocus and the first synthesized chord --
# without it the target app can process the paste keystroke before the
# clipboard update has settled and paste the previous value (0.1 s was
# empirically too short for WezTerm, 0.3 s reliable).
_PRE_PASTE_DELAY_S = 0.3


def _sequence_vks(sequence: str) -> list[list[int]]:
    """Comma-separated winhotkeys chords ("ctrl+shift+v,enter") -> VK codes
    per chord, in press order. Any unknown token discards the WHOLE sequence
    for plain Ctrl+V -- a partial run (paste chord dropped but a trailing
    Enter still fired) would be worse than a wrong paste chord, and a bad
    stored value must still paste, not silently do nothing."""
    try:
        return [
            [vk_key_names[token] for token in chord.split("+")] for chord in sequence.split(",")
        ]
    except KeyError:
        return [list(_FALLBACK_VKS)]


def paste_text(text: str, target_hwnd: int, chord: str = DEFAULT_PASTE_CHORD) -> None:
    if not text:
        return
    QApplication.clipboard().setText(text)
    # Qt puts a delayed-rendered data object on the OLE clipboard: the target
    # app's paste calls back into THIS process's GUI thread for the actual
    # text, which the time.sleep() between sequence chords below blocks --
    # the target then resolves to the previous clipboard value. Flushing
    # renders the text into the clipboard now, so no callback is needed.
    pythoncom.OleFlushClipboard()
    if target_hwnd:
        force_foreground(target_hwnd)
    time.sleep(_PRE_PASTE_DELAY_S)
    for index, vks in enumerate(_sequence_vks(chord)):
        if index:
            time.sleep(_INTER_CHORD_DELAY_S)
        for vk in vks:
            win32api.keybd_event(vk, 0, 0, 0)
        for vk in reversed(vks):
            win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)
