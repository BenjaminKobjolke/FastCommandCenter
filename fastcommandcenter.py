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

import win32gui  # noqa: E402
from command_palette import (  # noqa: E402
    CommandPalette,
    KeymapState,
    ListEntry,
    PaletteConfig,
    open_shortcut_editor_in_palette,
)
from command_palette.dialog import FilterListDialog  # noqa: E402
from command_palette.keymap import KeyMap  # noqa: E402
from command_palette.store import JsonStore, default_state_path  # noqa: E402
from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app_logger import AppLogger  # noqa: E402
from config.settings_store import APP_NAME, DEFAULT_BINDINGS, SettingsStore  # noqa: E402
from core.hotkey_bridge import HotkeyBridge  # noqa: E402
from core.hotkey_manager import HotkeyManager, winhotkeys_bindings  # noqa: E402
from core.hotkey_probe import HotkeyConflict  # noqa: E402
from core.single_instance import SingleInstance  # noqa: E402
from core.text_paste import paste_text  # noqa: E402
from core.tool_commands import ToolCommandsCallbacks, build_tool_commands  # noqa: E402
from core.window_activation import force_foreground  # noqa: E402
from core.window_process import exe_basename_for_hwnd  # noqa: E402
from gui.tray import build_tray  # noqa: E402
from palette.commands import PaletteWiring, build_commands  # noqa: E402


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
    palette_target_hwnd = 0

    def reinstall(keymap: KeyMap) -> list[HotkeyConflict]:
        """(Re)install every OS-global hotkey for ``keymap``, returning any
        chord some other program already owns -- see
        ``core/hotkey_manager.py``'s ``apply()``. Without this, a conflicting
        chord would bind here but silently never fire. Always logged
        (``apply()`` itself warns); callers with a live dialog additionally
        show ``_show_conflict_alert`` below."""
        return hotkey_manager.apply(keymap, bridge.on_hotkey)

    def _show_conflict_alert(dialog: FilterListDialog, conflicts: list[HotkeyConflict]) -> None:
        """In-palette alert for a chord that just got bound but is already
        held by another program -- this app's own design principle keeps every
        bit of user-facing feedback inside the palette window, never a
        separate dialog or tray balloon (see docs/COMMAND_PALETTE.md). Same
        pushed-level mechanism the shortcut editor itself uses for its
        reassign/clear confirms."""

        def _dismiss(_entry: ListEntry) -> None:
            dialog.pop_level()

        dialog.push_level(
            [ListEntry(title="OK", payload=None)],
            _dismiss,
            title="Shortcut already in use",
            placeholder="; ".join(
                f"{c.chord} is registered by another program and won't fire" for c in conflicts
            ),
        )

    def mount_shortcuts(dialog: FilterListDialog) -> None:
        """Drill the "Configure keyboard shortcuts" editor into the palette
        that's already open, in place -- see ``settings``'s ``on_navigate``."""

        def on_change(keymap: KeyMap) -> None:
            conflicts = reinstall(keymap)
            if conflicts:
                # Deferred: the library calls on_change from _finish_assign
                # *before* its own _refresh_command_list() -- pushing a level
                # here directly would have those rows stomped a moment later
                # (refresh_current_level replaces the current level's entries
                # in place, see dialog.py). Queuing lets that finish first,
                # same "let the current callback chain finish" pattern as
                # _raise_palette_to_foreground below.
                QTimer.singleShot(0, lambda: _show_conflict_alert(dialog, conflicts))

        open_shortcut_editor_in_palette(
            dialog,
            commands,
            keymap_state,
            on_change=on_change,
        )

    def _raise_palette_to_foreground() -> None:
        """Windows foreground-lock workaround -- see `core/window_activation.py`.
        Queued via QTimer.singleShot(0, ...) so it fires on the next event-loop
        turn, once the dialog `palette.open()` creates already exists as the
        active modal -- `exec()` hasn't returned yet, but its nested loop is
        spinning."""
        dialog = app.activeModalWidget() or app.activeWindow()
        if dialog is not None:
            force_foreground(int(dialog.winId()))

    def open_shortcuts_config() -> None:
        """Open the palette already drilled into the shortcut editor -- used
        by the tray action, the fresh-install prompt, and (via ``settings``'s
        ``run``) a global OS hotkey bound directly to "settings", which fires
        with no palette open yet."""
        _open_palette(navigate_to="settings")

    def apply_appearance(config: PaletteConfig) -> None:
        settings_store.set_appearance(config)
        palette.set_config(config)
        palette.restyle_open_dialog()

    def open_palette() -> None:
        _open_palette()

    def _open_palette(navigate_to: str | None = None, target_hwnd: int | None = None) -> None:
        nonlocal palette_target_hwnd
        if palette.is_open:
            # Already open: focus the live dialog instead of nesting a second
            # exec() loop. Keeps palette_target_hwnd (the original paste
            # target) untouched, and deliberately skips navigate_to --
            # re-drilling an open dialog would stack levels unpredictably.
            _raise_palette_to_foreground()
            return
        palette_target_hwnd = target_hwnd or win32gui.GetForegroundWindow()
        QTimer.singleShot(0, _raise_palette_to_foreground)
        palette.open(navigate_to=navigate_to)

    def paste_to_palette_target(text: str) -> None:
        chord = settings_store.paste_chord_for(exe_basename_for_hwnd(palette_target_hwnd))
        paste_text(text, palette_target_hwnd, chord)

    def open_paste_behaviour() -> None:
        """Open the palette drilled into the paste-behaviour chord list --
        `_open_palette` snapshots the foreground window first, so a hotkey
        pressed inside e.g. WezTerm configures WezTerm."""
        _open_palette(navigate_to="paste_behaviour")

    def open_text_provider(command_id: str) -> None:
        _open_palette(navigate_to=command_id)

    def request_quit() -> None:
        # Both callers (palette command, tray menu action) fire this from
        # inside a nested Qt event loop (the palette's dialog.exec(), the
        # tray menu's popup loop) -- a direct app.quit() there only exits
        # that inner loop and the process keeps running. Defer to the next
        # main-loop iteration so it actually terminates app.exec().
        QTimer.singleShot(0, app.quit)

    def yield_chords() -> list[str]:
        """The chords the host currently has registered globally, neutral
        format -- sent alongside every action fired at a tool so it can yield
        them back to the host while active (see CONTRACT.md's "Yielding
        hotkeys while a tool is active" and ``core/tool_commands.py``).
        Read fresh on every fire, not cached, so a rebind takes effect on the
        very next toggle."""
        return sorted({chord for chord, _ in winhotkeys_bindings(keymap_state.effective())})

    # Shared by both build_tool_commands() calls below -- the initial load and
    # refresh_tool_commands()'s reload after "Tools: manage folders" changes.
    tool_callbacks = ToolCommandsCallbacks(
        yield_chords=yield_chords,
        paste_text=paste_to_palette_target,
        open_text_provider=open_text_provider,
    )

    def refresh_tool_commands() -> None:
        """Rebuild the tool.* commands after ``settings_store``'s tool_dirs
        changed (see "Tools: manage folders"). Mutates ``commands``/``dispatch``
        IN PLACE (never reassigns the names) so every existing closure over
        them -- ``mount_shortcuts``, the hotkey dispatch lambda below, and
        ``palette``'s own reference -- sees the update without being touched.
        Reuses ``tool_bridge`` rather than building a new one, so instances it
        already launched stay tracked."""
        new_tool_commands, _ = build_tool_commands(settings_store, tool_bridge, tool_callbacks)
        commands[:] = [
            c for c in commands if not c.command_id.startswith("tool.")
        ] + new_tool_commands
        dispatch.clear()
        dispatch.update({command.command_id: command.run for command in commands})

    commands = build_commands(
        PaletteWiring(
            open_palette=open_palette,
            open_settings=open_shortcuts_config,
            mount_shortcuts=mount_shortcuts,
            quit_app=request_quit,
            settings_store=settings_store,
            apply_appearance=apply_appearance,
            refresh_tool_commands=refresh_tool_commands,
            paste_target_exe=lambda: exe_basename_for_hwnd(palette_target_hwnd),
            open_paste_behaviour=open_paste_behaviour,
        )
    )
    # One command per action declared by an external tool's fasttool.json --
    # see FastCommandCenter-tool-bridge/CONTRACT.md. tool_bridge owns any
    # tool instances it had to launch; torn down alongside the app below.
    tool_commands, tool_bridge = build_tool_commands(settings_store, callbacks=tool_callbacks)
    commands.extend(tool_commands)
    dispatch = {command.command_id: command.run for command in commands}

    palette = CommandPalette(commands, store=shared_store, config=settings_store.get_appearance())

    def activate_text_provider(activation) -> None:
        command_id = f"tool.{activation.tool_id}.text.{activation.provider_id}"
        target_hwnd = palette_target_hwnd or win32gui.GetForegroundWindow()

        def open_when_idle() -> None:
            if app.activeModalWidget() is not None:
                QTimer.singleShot(100, open_when_idle)
                return
            _open_palette(navigate_to=command_id, target_hwnd=target_hwnd)

        QTimer.singleShot(0, open_when_idle)

    tool_bridge.text_provider_activation_requested.connect(activate_text_provider)

    bridge.triggered.connect(lambda command_id: dispatch.get(command_id, lambda: None)())

    build_tray(
        app, open_palette, open_shortcuts_config, request_quit
    )  # app-parented inside; that keeps it alive
    # Startup conflicts are log-only (apply() already AppLogger.warns) -- no
    # palette dialog exists yet at boot to alert inside, see mount_shortcuts.
    reinstall(keymap_state.effective())

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
