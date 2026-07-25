"""Wraps winhotkeys.HotkeyHandler with start/stop/update semantics."""

from __future__ import annotations

from collections.abc import Callable

from winhotkeys import HotkeyHandler

from app_logger import AppLogger


class HotkeyManager:
    """Owns one global (OS-level) hotkey registration; restarts on rebind."""

    def __init__(self, hotkey: str, callback: Callable[[], None]) -> None:
        self.hotkey = hotkey
        self.callback = callback
        self.handler: HotkeyHandler | None = None

    def start(self) -> None:
        """Start listening for the hotkey."""
        if self.handler:
            self.stop()
        AppLogger.info(f"Registering global hotkey: {self.hotkey}")
        self.handler = HotkeyHandler(self.hotkey, self.callback, suppress=True)
        self.handler.start()

    def stop(self) -> None:
        """Stop listening for the hotkey."""
        if self.handler:
            self.handler.stop()
            self.handler = None

    def update_hotkey(self, new_hotkey: str) -> None:
        """Rebind to a new hotkey combination, restarting the listener."""
        if new_hotkey != self.hotkey:
            self.hotkey = new_hotkey
            self.start()

    def is_running(self) -> bool:
        """Check if the hotkey handler is running."""
        return self.handler is not None
