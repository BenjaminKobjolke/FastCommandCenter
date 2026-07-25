"""Single instance manager for FastCommandCenter.

A duplicate background instance would double-register the global hotkey (one of the
two registrations fails or steals the other's callback) and show two tray icons, so a
second launch just exits.
"""

from __future__ import annotations

import win32api
import win32event
import winerror

from app_logger import AppLogger


class SingleInstance:
    """Ensures only one instance runs at a time, using a named Win32 mutex."""

    def __init__(self, mutex_name: str = "Global\\FastCommandCenter_SingleInstance_Mutex") -> None:
        self.mutex_name = mutex_name
        self.mutex = None
        self._is_first = False

        try:
            # pywin32 stubs mistype lpMutexAttributes as required; None is the documented
            # "default security" value.
            self.mutex = win32event.CreateMutex(None, False, self.mutex_name)  # type: ignore[arg-type]
            already_running = win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS
            self._is_first = not already_running
            if already_running:
                AppLogger.info(f"Another instance is already running (mutex: {self.mutex_name})")
            else:
                AppLogger.debug(f"First instance started (mutex: {self.mutex_name})")
        except Exception as e:
            AppLogger.error(f"Error creating mutex: {e}")
            self._is_first = True  # default to allowing startup if mutex creation fails

    def is_first_instance(self) -> bool:
        """Check if this is the first instance of the application."""
        return self._is_first

    def cleanup(self) -> None:
        """Release the mutex. Call when the application exits."""
        if self.mutex:
            try:
                # pywin32 stubs mistype the handle param as int; PyHANDLE is the real runtime type.
                win32api.CloseHandle(self.mutex)  # type: ignore[arg-type]
                AppLogger.debug("Mutex released")
            except Exception as e:
                AppLogger.error(f"Error releasing mutex: {e}")
            finally:
                self.mutex = None

    def __del__(self) -> None:
        self.cleanup()
