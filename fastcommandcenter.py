#!/usr/bin/env python3
"""FastCommandCenter - global-hotkey command palette, no main window."""

import os
import sys

# Add current directory to path for absolute imports (core., config., gui., palette.)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# winhotkeys prints diagnostics containing non-ASCII characters (e.g. "→").
# Under the default Windows console codepage (cp1252) that raises UnicodeEncodeError
# on its background registration thread, killing it before it ever reaches the
# message pump -- so the hotkey gets registered at the OS level but never fires.
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from command_palette import CommandPalette, PaletteConfig  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app_logger import AppLogger  # noqa: E402
from config.settings_store import SettingsStore  # noqa: E402
from core.hotkey_bridge import HotkeyBridge  # noqa: E402
from core.hotkey_manager import HotkeyManager  # noqa: E402
from core.single_instance import SingleInstance  # noqa: E402
from gui.settings_dialog import SettingsDialog  # noqa: E402
from gui.tray import build_tray  # noqa: E402
from palette.commands import build_commands  # noqa: E402


def main() -> None:
    single_instance = SingleInstance()
    if not single_instance.is_first_instance():
        AppLogger.info("Exiting: another instance is already running")
        sys.exit(0)

    app = QApplication(sys.argv)
    app.setApplicationName("FastCommandCenter")
    app.setQuitOnLastWindowClosed(False)  # background app: closing a dialog must not exit it

    settings_store = SettingsStore()
    bridge = HotkeyBridge()
    hotkey_manager = HotkeyManager(settings_store.get_chord(), bridge.on_hotkey)

    def open_settings() -> None:
        SettingsDialog(settings_store, hotkey_manager).exec()

    palette = CommandPalette(
        build_commands(open_settings, app.quit),
        config=PaletteConfig(frameless=True),
    )

    def open_palette() -> None:
        palette.open()
        # Opening from a background process may not steal focus by default.
        # (Verify at runtime; command-palette's dialog handles its own show/raise
        # via QDialog.exec(), so this is only needed if focus-stealing is observed.)

    bridge.triggered.connect(open_palette)
    hotkey_manager.start()

    build_tray(app, open_palette, open_settings)  # app-parented inside; that keeps it alive

    app.aboutToQuit.connect(hotkey_manager.stop)
    app.aboutToQuit.connect(single_instance.cleanup)

    if not settings_store.has_chord():
        open_settings()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
