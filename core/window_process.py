"""Resolve the exe behind a window handle -- keys the per-app paste overrides."""

from __future__ import annotations

import os

import pywintypes
import win32api
import win32con
import win32process


def exe_basename_for_hwnd(hwnd: int) -> str | None:
    """Lowercase exe basename (e.g. "wezterm-gui.exe") of the process owning
    ``hwnd``, or None when it can't be resolved (hwnd 0, window gone, or an
    elevated process this one may not open)."""
    if not hwnd:
        return None
    try:
        pid = win32process.GetWindowThreadProcessId(hwnd)[1]
        handle = win32api.OpenProcess(
            win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, False, pid
        )
        try:
            path = win32process.GetModuleFileNameEx(handle, 0)
        finally:
            win32api.CloseHandle(handle)
    except pywintypes.error:
        return None
    return os.path.basename(path).lower() or None
