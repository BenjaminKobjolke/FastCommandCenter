"""Turns fasttool.json manifests (via fasttool_host.ToolBridge) into palette
Commands.

See FastCommandCenter-tool-bridge/CONTRACT.md for the wire protocol. Each
declared tool action becomes one ordinary Command -- bindable in the palette
and by a global hotkey, no different from any built-in command. The Command's
`run` just fires the action at the tool; `fasttool_host` owns finding or
launching it.

Each manifest also gets one navigable "<name>: settings" Command
(CONTRACT.md's "Settings protocol (v2)") -- picking it in an already-open
palette drills into core/tool_settings_editor.py's live editor. Like
`Appearance: ...` and `Tools: manage folders` (palette/commands.py), this is
drill-in-only -- no direct-hotkey-when-closed support like `settings` has,
see that module's `_NO_RUN`.

Text-provider commands support both paths: `on_navigate` drills into an
already-open palette, while `run` asks FCC to open directly at that provider
when its global shortcut fires.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from command_palette import Command
from command_palette.dialog import FilterListDialog
from fasttool_host import ToolAction, ToolBridge, ToolTextProviderDef

from config.settings_store import SettingsStore
from core.tool_settings_editor import open_tool_settings_editor_in_palette
from core.tool_text_provider import open_tool_text_provider_in_palette

_NO_RUN: Callable[[], None] = lambda: None  # noqa: E731 — navigable commands never run() directly


@dataclass(frozen=True)
class ToolCommandsCallbacks:
    """The callback swarm build_tool_commands() needs, bundled. settings_store
    and bridge stay separate params -- bridge varies per call (None first,
    reused after) and is also returned, unlike these fixed callbacks."""

    yield_chords: Callable[[], list[str]] | None = None
    paste_text: Callable[[str], None] = lambda _text: None  # noqa: E731
    open_text_provider: Callable[[str], None] = lambda _command_id: None  # noqa: E731


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


def _make_on_navigate(
    bridge: ToolBridge, tool_id: str, tool_name: str
) -> Callable[[FilterListDialog], None]:
    # Same late-binding fix as _make_run's: fixes tool_id/tool_name per-call
    # rather than closing over a comprehension's loop variable.
    def on_navigate(dialog: FilterListDialog) -> None:
        open_tool_settings_editor_in_palette(dialog, tool_id, tool_name, bridge)

    return on_navigate


def _make_text_on_navigate(
    bridge: ToolBridge,
    tool_id: str,
    provider: ToolTextProviderDef,
    paste_text: Callable[[str], None],
) -> Callable[[FilterListDialog], None]:
    def on_navigate(dialog: FilterListDialog) -> None:
        open_tool_text_provider_in_palette(dialog, tool_id, provider, bridge, paste_text)

    return on_navigate


def _make_text_run(
    command_id: str,
    open_text_provider: Callable[[str], None],
) -> Callable[[], None]:
    def run() -> None:
        open_text_provider(command_id)

    return run


def build_tool_commands(
    settings_store: SettingsStore,
    bridge: ToolBridge | None = None,
    callbacks: ToolCommandsCallbacks | None = None,
) -> tuple[list[Command], ToolBridge]:
    """Load every fasttool.json under ``settings_store.get_tool_dirs()`` and
    return one Command per declared action plus one navigable "<name>:
    settings" Command per tool, plus the ToolBridge that fires/describes/sets
    them. Callers own the bridge's lifecycle -- call ``bridge.shutdown()`` on
    app quit to terminate any tool instances it launched.

    Pass an existing ``bridge`` to reload after ``tool_dirs`` changes -- a
    fresh ``ToolBridge()`` would lose track of any instances the original one
    already launched.

    ``callbacks.yield_chords``, if given, is called fresh on every fire and its
    result (the host's currently-registered chords, neutral format) is sent
    alongside the action -- see CONTRACT.md's "Yielding hotkeys while a tool
    is active". This is how a global hotkey bound to a tool's own action
    (e.g. a toggle) keeps working after the tool goes active and installs its
    own keyboard hook, which would otherwise be able to swallow that chord
    before the host's `RegisterHotKey` ever sees it.
    """
    bridge = bridge if bridge is not None else ToolBridge()
    callbacks = callbacks if callbacks is not None else ToolCommandsCallbacks()
    actions = bridge.load([Path(tool_dir) for tool_dir in settings_store.get_tool_dirs()])
    action_commands = [
        Command(
            command_id=action.command_id,
            title=action.title,
            run=_make_run(bridge, action, callbacks.yield_chords),
        )
        for action in actions
    ]
    settings_commands = [
        Command(
            command_id=f"tool.{manifest.id}.settings",
            title=f"{manifest.name}: settings",
            run=_NO_RUN,
            on_navigate=_make_on_navigate(bridge, manifest.id, manifest.name),
        )
        for manifest in bridge.manifests
    ]
    text_commands = [
        Command(
            command_id=f"tool.{manifest.id}.text.{provider.id}",
            title=provider.label,
            run=_make_text_run(
                f"tool.{manifest.id}.text.{provider.id}", callbacks.open_text_provider
            ),
            on_navigate=_make_text_on_navigate(bridge, manifest.id, provider, callbacks.paste_text),
        )
        for manifest in bridge.manifests
        for provider in manifest.text_providers
    ]
    return action_commands + text_commands + settings_commands, bridge
