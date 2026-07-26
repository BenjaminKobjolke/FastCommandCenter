"""Force a window owned by this background process to the foreground.

FastCommandCenter is a tray/hotkey app -- it is never the foreground process.
`python-command-palette`'s dialog does no activation of its own (plain
`QDialog.exec()`), so Windows' foreground lock silently keeps the palette from
coming to the front the first time it's opened via the global hotkey. Once the
user opens it once via the tray (a genuine interaction with this process),
Windows grants it foreground rights and every later open works -- see
``fastcommandcenter.py``'s ``open_palette``/``open_shortcuts_config`` for the
call sites.
"""

from __future__ import annotations

import win32api
import win32con
import win32gui
import win32process

from app_logger import AppLogger


def force_foreground(hwnd: int) -> None:
    """Bring ``hwnd`` to the foreground even though this process isn't.

    Windows only lets the current foreground thread hand off foreground
    rights. Attaching our input thread to the current foreground window's
    thread lifts that restriction for the duration of the call; detaching
    afterward restores normal behavior for both threads.
    """
    if not hwnd:
        return
    foreground_hwnd = win32gui.GetForegroundWindow()
    if not foreground_hwnd or foreground_hwnd == hwnd:
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        win32gui.SetForegroundWindow(hwnd)
        return

    current_thread_id = win32api.GetCurrentThreadId()
    foreground_thread_id = win32process.GetWindowThreadProcessId(foreground_hwnd)[0]

    attached = False
    if foreground_thread_id != current_thread_id:
        try:
            win32process.AttachThreadInput(current_thread_id, foreground_thread_id, True)
            attached = True
        except win32gui.error:
            AppLogger.warning("force_foreground: AttachThreadInput failed, activating anyway")

    try:
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        win32gui.SetForegroundWindow(hwnd)
        win32gui.BringWindowToTop(hwnd)
    finally:
        if attached:
            win32process.AttachThreadInput(current_thread_id, foreground_thread_id, False)
