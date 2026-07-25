"""Marshals the winhotkeys callback (fired on its own thread) onto the Qt GUI thread.

A Qt dialog can only be shown safely from the thread that owns the QApplication.
winhotkeys invokes its callback on a background message-pump thread, so the callback
must not touch Qt directly. Connecting to `triggered` with Qt's default (auto) connection
type resolves to a queued connection here, since emit() happens off the GUI thread —
the connected slot then runs on the GUI thread instead.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class HotkeyBridge(QObject):
    """Emits `triggered` from any thread; connected slots run on this object's thread."""

    triggered = Signal()

    def on_hotkey(self) -> None:
        """Pass this as the winhotkeys callback."""
        self.triggered.emit()
