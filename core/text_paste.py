"""Paste text into the window that owned focus before FCC opened."""

from __future__ import annotations

import time

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
_INTER_CHORD_DELAY_S = 0.1


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
    if target_hwnd:
        force_foreground(target_hwnd)
    for index, vks in enumerate(_sequence_vks(chord)):
        if index:
            time.sleep(_INTER_CHORD_DELAY_S)
        for vk in vks:
            win32api.keybd_event(vk, 0, 0, 0)
        for vk in reversed(vks):
            win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)
