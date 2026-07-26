"""Turns fasttool.json manifests (via fasttool_host.ToolBridge) into palette
Commands.

See FastCommandCenter-tool-bridge/CONTRACT.md for the wire protocol. Each
declared tool action becomes one ordinary Command -- bindable in the palette
and by a global hotkey, no different from any built-in command. The Command's
`run` just fires the action at the tool; `fasttool_host` owns finding or
launching it.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from command_palette import Command
from fasttool_host import ToolAction, ToolBridge

from config.settings_store import SettingsStore


def _make_run(
    bridge: ToolBridge, action: ToolAction, yield_chords: Callable[[], list[str]] | None
) -> Callable[[], None]:
    # A plain closure over the comprehension's loop variable would late-bind
    # to whichever action was last in the list -- this factory's own
    # `action` parameter fixes it per-call instead.
    def run() -> None:
        chords = yield_chords() if yield_chords is not None else None
        bridge.fire(action.tool_id, action.action_id, yield_chords=chords)

    return run


def build_tool_commands(
    settings_store: SettingsStore,
    bridge: ToolBridge | None = None,
    yield_chords: Callable[[], list[str]] | None = None,
) -> tuple[list[Command], ToolBridge]:
    """Load every fasttool.json under ``settings_store.get_tool_dirs()`` and
    return one Command per declared action, plus the ToolBridge that fires
    them. Callers own the bridge's lifecycle -- call ``bridge.shutdown()`` on
    app quit to terminate any tool instances it launched.

    Pass an existing ``bridge`` to reload after ``tool_dirs`` changes -- a
    fresh ``ToolBridge()`` would lose track of any instances the original one
    already launched.

    ``yield_chords``, if given, is called fresh on every fire and its result
    (the host's currently-registered chords, neutral format) is sent
    alongside the action -- see CONTRACT.md's "Yielding hotkeys while a tool
    is active". This is how a global hotkey bound to a tool's own action
    (e.g. a toggle) keeps working after the tool goes active and installs its
    own keyboard hook, which would otherwise be able to swallow that chord
    before the host's `RegisterHotKey` ever sees it.
    """
    bridge = bridge if bridge is not None else ToolBridge()
    actions = bridge.load([Path(tool_dir) for tool_dir in settings_store.get_tool_dirs()])
    commands = [
        Command(
            command_id=action.command_id,
            title=action.title,
            run=_make_run(bridge, action, yield_chords),
        )
        for action in actions
    ]
    return commands, bridge
