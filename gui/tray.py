"""System tray icon: reach the palette, Settings, and Quit without a main window."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon


class FastCommandTrayIcon(QSystemTrayIcon):
    """Tray icon that keeps its context menu alive."""

    def __init__(self, icon: QIcon, app: QApplication) -> None:
        super().__init__(icon, app)
        self.menu_ref: QMenu | None = None


def build_tray(
    app: QApplication,
    open_palette: Callable[[], None],
    open_settings: Callable[[], None],
) -> QSystemTrayIcon:
    """Create, wire, and show the tray icon with its context menu."""
    icon = app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
    tray = FastCommandTrayIcon(icon, app)  # app-parented: survives after this function returns
    tray.setToolTip("FastCommandCenter")

    menu = QMenu()
    menu.addAction("Open palette", open_palette)
    menu.addAction("Settings", open_settings)
    menu.addSeparator()
    menu.addAction("Quit", app.quit)
    tray.setContextMenu(menu)
    tray.menu_ref = menu  # QSystemTrayIcon doesn't own the menu; keep a ref so it isn't GC'd

    tray.show()
    return tray
