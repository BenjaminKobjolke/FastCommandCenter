"""Marshals a winhotkeys callback (fired on its own thread) onto the Qt GUI thread.

A Qt dialog can only be shown safely from the thread that owns the QApplication.
winhotkeys invokes its callback on a background message-pump thread, so the callback
must not touch Qt directly. Connecting to `triggered` with Qt's default (auto) connection
type resolves to a queued connection here, since emit() happens off the GUI thread —
the connected slot then runs on the GUI thread instead.

Carries the fired binding's command id, since one `HotkeyManager` now registers
many bindings (see `core/hotkey_manager.py`) instead of a single opener chord.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class HotkeyBridge(QObject):
    """Emits `triggered(command_id)` from any thread; the connected slot runs
    on this object's thread."""

    triggered = Signal(str)

    def on_hotkey(self, command_id: str) -> None:
        """Pass as the (per-binding) winhotkeys callback, e.g. via a small lambda
        that closes over ``command_id`` -- see `HotkeyManager.apply`."""
        self.triggered.emit(command_id)
