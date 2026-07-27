"""Paste text into the window that owned focus before FCC opened."""

from __future__ import annotations

import win32api
import win32con
from PySide6.QtWidgets import QApplication

from core.window_activation import force_foreground


def paste_text(text: str, target_hwnd: int) -> None:
    if not text:
        return
    QApplication.clipboard().setText(text)
    if target_hwnd:
        force_foreground(target_hwnd)
    win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
    win32api.keybd_event(ord("V"), 0, 0, 0)
    win32api.keybd_event(ord("V"), 0, win32con.KEYEVENTF_KEYUP, 0)
    win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
