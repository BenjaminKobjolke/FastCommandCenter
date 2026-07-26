"""fasttool.json manifest -> palette Command mapping.

Only the construction step is exercised here (command_id/title derivation,
one Command per declared action) -- calling a Command's `run` would reach
into fasttool_host.ToolBridge.fire()'s QProcess/QTimer machinery, which needs
a live Qt event loop, same reason core/hotkey_manager.py's `apply()` isn't
unit-tested either (see tests/unit/test_hotkey_manager.py).
"""

import json
from pathlib import Path

from command_palette import MemoryStore

from config.settings_store import SettingsStore
from core.tool_commands import build_tool_commands

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
    tool_dir = tmp_path / "FastKeyboardMouse"
    _write_manifest(tool_dir, VALID_MANIFEST)
    settings_store = SettingsStore(MemoryStore())
    settings_store.set_tool_dirs([str(tool_dir)])

    commands, _bridge = build_tool_commands(settings_store)

    assert [c.command_id for c in commands] == ["tool.fastkeyboardmouse.toggle"]
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
    }


def test_tool_dir_without_manifest_is_skipped(tmp_path: Path):
    empty_dir = tmp_path / "no-manifest-here"
    empty_dir.mkdir()
    settings_store = SettingsStore(MemoryStore())
    settings_store.set_tool_dirs([str(empty_dir)])

    commands, _bridge = build_tool_commands(settings_store)

    assert commands == []


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
