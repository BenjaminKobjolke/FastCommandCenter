"""fasttool.json manifest -> palette Command mapping.

Only the construction step is exercised here (command_id/title derivation,
one Command per declared action) -- calling a Command's `run` would reach
into fasttool_host.ToolBridge.fire()'s QProcess/QTimer machinery, which needs
a live Qt event loop, same reason core/hotkey_manager.py's `apply()` isn't
unit-tested either (see tests/unit/test_hotkey_manager.py).
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

from command_palette import MemoryStore
from fasttool_host import ToolBridge

from config.settings_store import SettingsStore
from core.tool_commands import ToolCommandsCallbacks, build_tool_commands

VALID_MANIFEST = {
    "id": "fastkeyboardmouse",
    "name": "Fast Keyboard Mouse",
    "ipc_title": "FastToolIPC::fastkeyboardmouse",
    "launch": {"exe": "FastKeyboardMouse.exe", "args": ["--palette"]},
    "actions": [{"id": "toggle", "label": "Toggle mouse mode"}],
}


def _write_manifest(tool_dir: Path, data: dict) -> None:
    tool_dir.mkdir()
    (tool_dir / "fasttool.json").write_text(json.dumps(data), encoding="utf-8")


def test_no_tool_dirs_configured_yields_no_commands():
    settings_store = SettingsStore(MemoryStore())

    commands, _bridge = build_tool_commands(settings_store)

    assert commands == []


def test_one_command_per_declared_action(tmp_path: Path):
    # Plus one navigable "<name>: settings" command per tool (CONTRACT.md's
    # "Settings protocol (v2)") -- see test_one_settings_command_per_tool
    # below for that command's own construction.
    tool_dir = tmp_path / "FastKeyboardMouse"
    _write_manifest(tool_dir, VALID_MANIFEST)
    settings_store = SettingsStore(MemoryStore())
    settings_store.set_tool_dirs([str(tool_dir)])

    commands, _bridge = build_tool_commands(settings_store)

    assert [c.command_id for c in commands] == [
        "tool.fastkeyboardmouse.toggle",
        "tool.fastkeyboardmouse.settings",
    ]
    assert commands[0].title == "Fast Keyboard Mouse: Toggle mouse mode"


def test_multi_action_tool_yields_one_command_each(tmp_path: Path):
    tool_dir = tmp_path / "FastTextSuggester"
    _write_manifest(
        tool_dir,
        {
            **VALID_MANIFEST,
            "id": "fasttextsuggester",
            "ipc_title": "FastToolIPC::fasttextsuggester",
            "actions": [
                {"id": "capture", "label": "Capture"},
                {"id": "suggestion", "label": "Suggestion"},
            ],
        },
    )
    settings_store = SettingsStore(MemoryStore())
    settings_store.set_tool_dirs([str(tool_dir)])

    commands, _bridge = build_tool_commands(settings_store)

    assert {c.command_id for c in commands} == {
        "tool.fasttextsuggester.capture",
        "tool.fasttextsuggester.suggestion",
        "tool.fasttextsuggester.settings",
    }


def test_text_provider_yields_one_navigable_and_runnable_command(tmp_path: Path):
    tool_dir = tmp_path / "FastTextSuggester"
    _write_manifest(
        tool_dir,
        {
            **VALID_MANIFEST,
            "id": "fasttextsuggester",
            "ipc_title": "FastToolIPC::fasttextsuggester",
            "text_providers": [{"id": "suggestions", "label": "FastTextSuggester"}],
        },
    )
    settings_store = SettingsStore(MemoryStore())
    settings_store.set_tool_dirs([str(tool_dir)])

    opened = []
    commands, _bridge = build_tool_commands(
        settings_store, callbacks=ToolCommandsCallbacks(open_text_provider=opened.append)
    )
    command = next(c for c in commands if c.command_id.endswith("text.suggestions"))

    assert command.title == "FastTextSuggester"
    assert command.on_navigate is not None
    command.run()
    assert opened == ["tool.fasttextsuggester.text.suggestions"]


def test_tool_dir_without_manifest_is_skipped(tmp_path: Path):
    empty_dir = tmp_path / "no-manifest-here"
    empty_dir.mkdir()
    settings_store = SettingsStore(MemoryStore())
    settings_store.set_tool_dirs([str(empty_dir)])

    commands, _bridge = build_tool_commands(settings_store)

    assert commands == []


def test_run_fires_with_yield_chords_read_fresh_from_the_provider(tmp_path: Path):
    # yield_chords must be called at fire time, not baked in at build time --
    # a rebind between builds (there is none here) or between two fires of
    # the same command must be reflected on the very next fire.
    tool_dir = tmp_path / "FastKeyboardMouse"
    _write_manifest(tool_dir, VALID_MANIFEST)
    settings_store = SettingsStore(MemoryStore())
    settings_store.set_tool_dirs([str(tool_dir)])
    fake_bridge = MagicMock(spec=ToolBridge)
    fake_bridge.load.return_value = ToolBridge().load([tool_dir])
    chords = ["alt+q"]

    commands, _bridge = build_tool_commands(
        settings_store, fake_bridge, ToolCommandsCallbacks(yield_chords=lambda: chords)
    )
    commands[0].run()

    fake_bridge.fire.assert_called_once_with("fastkeyboardmouse", "toggle", yield_chords=["alt+q"])


def test_run_passes_none_when_no_yield_chords_provider_given(tmp_path: Path):
    tool_dir = tmp_path / "FastKeyboardMouse"
    _write_manifest(tool_dir, VALID_MANIFEST)
    settings_store = SettingsStore(MemoryStore())
    settings_store.set_tool_dirs([str(tool_dir)])
    fake_bridge = MagicMock(spec=ToolBridge)
    fake_bridge.load.return_value = ToolBridge().load([tool_dir])

    commands, _bridge = build_tool_commands(settings_store, fake_bridge)
    commands[0].run()

    fake_bridge.fire.assert_called_once_with("fastkeyboardmouse", "toggle", yield_chords=None)


def test_reloading_with_the_same_bridge_reuses_it_not_a_fresh_one(tmp_path: Path):
    # A refresh (tool_dirs changed) must reuse the caller's bridge -- a new
    # ToolBridge() would lose track of any instances the original launched.
    tool_dir = tmp_path / "FastKeyboardMouse"
    _write_manifest(tool_dir, VALID_MANIFEST)
    settings_store = SettingsStore(MemoryStore())
    settings_store.set_tool_dirs([str(tool_dir)])
    _first_commands, bridge = build_tool_commands(settings_store)

    settings_store.set_tool_dirs([])
    second_commands, second_bridge = build_tool_commands(settings_store, bridge)

    assert second_bridge is bridge
    assert second_commands == []
