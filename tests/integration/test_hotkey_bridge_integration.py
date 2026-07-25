"""Integration test for the cross-thread hotkey dispatch (core gotcha of this app):
winhotkeys fires its callback on a background thread; HotkeyBridge must marshal that
onto the Qt GUI thread before any widget code runs. Requires QT_QPA_PLATFORM=offscreen
in headless environments (set by tools/run_integration_tests.bat).
"""

import threading

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from core.hotkey_bridge import HotkeyBridge


def test_triggered_runs_on_gui_thread_when_emitted_from_background_thread():
    QApplication.instance() or QApplication([])
    gui_thread = QCoreApplication.instance().thread()

    bridge = HotkeyBridge()
    seen_thread = {}
    seen_command_id = {}

    def on_triggered(command_id):
        seen_thread["thread"] = threading.current_thread()
        seen_command_id["id"] = command_id
        loop.quit()

    bridge.triggered.connect(on_triggered)

    def fire_from_background():
        bridge.on_hotkey("open_palette")

    worker = threading.Thread(target=fire_from_background)

    loop = QEventLoop()
    QTimer.singleShot(0, worker.start)
    QTimer.singleShot(2000, loop.quit)  # safety timeout
    loop.exec()
    worker.join(timeout=1)

    assert "thread" in seen_thread, "slot never ran"
    assert seen_thread["thread"] is threading.main_thread()
    assert seen_command_id["id"] == "open_palette"
    assert QApplication.instance().thread() is gui_thread
