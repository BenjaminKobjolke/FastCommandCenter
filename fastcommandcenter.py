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

from command_palette import (  # noqa: E402
    CommandPalette,
    KeymapState,
    PaletteConfig,
    open_shortcut_editor_in_palette,
)
from command_palette.dialog import FilterListDialog  # noqa: E402
from command_palette.store import JsonStore, default_state_path  # noqa: E402
from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app_logger import AppLogger  # noqa: E402
from config.settings_store import APP_NAME, DEFAULT_BINDINGS, SettingsStore  # noqa: E402
from core.hotkey_bridge import HotkeyBridge  # noqa: E402
from core.hotkey_manager import HotkeyManager  # noqa: E402
from core.single_instance import SingleInstance  # noqa: E402
from core.tool_commands import build_tool_commands  # noqa: E402
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

    # One shared store for this app's own settings (appearance, the legacy
    # single-hotkey key) and the palette library's `key_bindings` -- every
    # command's global hotkey(s) live there via KeymapState.
    shared_store = JsonStore(default_state_path(APP_NAME))
    settings_store = SettingsStore(shared_store)
    keymap_state = KeymapState(shared_store, DEFAULT_BINDINGS)
    settings_store.migrate_legacy_chord(keymap_state)

    bridge = HotkeyBridge()
    hotkey_manager = HotkeyManager()

    def mount_shortcuts(dialog: FilterListDialog) -> None:
        """Drill the "Configure keyboard shortcuts" editor into the palette
        that's already open, in place -- see ``settings``'s ``on_navigate``."""
        open_shortcut_editor_in_palette(
            dialog,
            commands,
            keymap_state,
            on_change=lambda keymap: hotkey_manager.apply(keymap, bridge.on_hotkey),
        )

    def open_shortcuts_config() -> None:
        """Open the palette already drilled into the shortcut editor -- used
        by the tray action, the fresh-install prompt, and (via ``settings``'s
        ``run``) a global OS hotkey bound directly to "settings", which fires
        with no palette open yet."""
        palette.open(navigate_to="settings")

    def apply_appearance(config: PaletteConfig) -> None:
        settings_store.set_appearance(config)
        palette.set_config(config)
        palette.restyle_open_dialog()

    def open_palette() -> None:
        palette.open()
        # Opening from a background process may not steal focus by default.
        # (Verify at runtime; command-palette's dialog handles its own show/raise
        # via QDialog.exec(), so this is only needed if focus-stealing is observed.)

    def request_quit() -> None:
        # Both callers (palette command, tray menu action) fire this from
        # inside a nested Qt event loop (the palette's dialog.exec(), the
        # tray menu's popup loop) -- a direct app.quit() there only exits
        # that inner loop and the process keeps running. Defer to the next
        # main-loop iteration so it actually terminates app.exec().
        QTimer.singleShot(0, app.quit)

    def refresh_tool_commands() -> None:
        """Rebuild the tool.* commands after ``settings_store``'s tool_dirs
        changed (see "Tools: manage folders"). Mutates ``commands``/``dispatch``
        IN PLACE (never reassigns the names) so every existing closure over
        them -- ``mount_shortcuts``, the hotkey dispatch lambda below, and
        ``palette``'s own reference -- sees the update without being touched.
        Reuses ``tool_bridge`` rather than building a new one, so instances it
        already launched stay tracked."""
        new_tool_commands, _ = build_tool_commands(settings_store, tool_bridge)
        commands[:] = [
            c for c in commands if not c.command_id.startswith("tool.")
        ] + new_tool_commands
        dispatch.clear()
        dispatch.update({command.command_id: command.run for command in commands})

    commands = build_commands(
        open_palette,
        open_shortcuts_config,
        mount_shortcuts,
        request_quit,
        settings_store,
        apply_appearance,
        refresh_tool_commands,
    )
    # One command per action declared by an external tool's fasttool.json --
    # see FastCommandCenter-tool-bridge/CONTRACT.md. tool_bridge owns any
    # tool instances it had to launch; torn down alongside the app below.
    tool_commands, tool_bridge = build_tool_commands(settings_store)
    commands.extend(tool_commands)
    dispatch = {command.command_id: command.run for command in commands}

    palette = CommandPalette(commands, store=shared_store, config=settings_store.get_appearance())

    bridge.triggered.connect(lambda command_id: dispatch.get(command_id, lambda: None)())
    hotkey_manager.apply(keymap_state.effective(), bridge.on_hotkey)

    build_tray(
        app, open_palette, open_shortcuts_config, request_quit
    )  # app-parented inside; that keeps it alive

    app.aboutToQuit.connect(hotkey_manager.stop)
    app.aboutToQuit.connect(single_instance.cleanup)
    app.aboutToQuit.connect(tool_bridge.shutdown)

    if keymap_state.effective().bindings == tuple(DEFAULT_BINDINGS):
        # Nothing has ever been customized (fresh install, or a legacy chord
        # that matched the default and so migrated to nothing) -- surface the
        # editor once so the user knows shortcuts are configurable.
        open_shortcuts_config()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
