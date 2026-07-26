"""core/tool_settings_editor.py's in-palette settings editor.

Driven through fake dialog/bridge stubs rather than a real FilterListDialog/
ToolBridge -- no QApplication, no win32 IPC needed to exercise the actual
row-building / per-type-dispatch / apply logic. `bridge.settings_received` is
a tiny connect/emit stand-in (not a real Qt Signal) so a test can simulate an
async snapshot arriving via the exact same connect() path production code
uses, without a spun Qt event loop.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fasttool_host import ToolSettings

from core.tool_settings_editor import open_tool_settings_editor_in_palette


class _FakeSignal:
    """Stand-in for a Qt Signal: enough of connect/disconnect/emit to drive
    the editor's connect-per-request lifecycle without a real QObject."""

    def __init__(self) -> None:
        self._slots: list = []

    def connect(self, slot) -> None:
        self._slots.append(slot)

    def disconnect(self, slot) -> None:
        self._slots.remove(slot)  # raises ValueError if absent, like Qt raising on a bad disconnect

    def emit(self, *args) -> None:
        for slot in list(self._slots):
            slot(*args)


class _FakeDialog:
    """Stand-in for FilterListDialog: records push_level/push_capture_level/
    refresh_current_level/pop_level calls instead of rendering anything."""

    def __init__(self) -> None:
        self.levels: list[dict] = []
        self.captures: list[dict] = []
        self.refreshed: list[list] = []
        self.pop_count = 0

    def push_level(self, entries, on_choose, *, title="", placeholder="", on_delete=None):
        self.levels.append({"entries": entries, "on_choose": on_choose, "title": title})

    def push_capture_level(self, on_chord, *, title="", prompt="", detected_fmt=""):
        self.captures.append({"on_chord": on_chord, "title": title})

    def refresh_current_level(self, entries):
        self.refreshed.append(entries)

    def pop_level(self):
        self.pop_count += 1
        return True

    # --- test helpers -------------------------------------------------------

    def current_entries(self):
        """Whatever a real dialog would currently be showing: the last
        refresh, or the last pushed level's entries if nothing refreshed yet."""
        if self.refreshed:
            return self.refreshed[-1]
        return self.levels[-1]["entries"]

    def root_on_choose(self):
        return self.levels[0]["on_choose"]


def _fake_bridge() -> MagicMock:
    bridge = MagicMock()
    bridge.settings_received = _FakeSignal()
    return bridge


SNAPSHOT = ToolSettings.from_dict(
    {
        "tool_id": "fastkeyboardmouse",
        "settings": [
            {"id": "ToggleKey", "label": "Toggle mouse mode", "type": "shortcut", "value": "alt+q"},
            {
                "id": "BaseSpeed",
                "label": "Cursor speed",
                "type": "int",
                "value": 5,
                "min": 1,
                "max": 10,
                "step": 1,
            },
            {"id": "DarkMode", "label": "Dark mode", "type": "bool", "value": True},
            {
                "id": "SpeedModifier",
                "label": "Speed boost key",
                "type": "enum",
                "value": "Shift",
                "choices": ["Shift", "Ctrl", "Alt"],
            },
            {
                "id": "IndicatorColor",
                "label": "Indicator color",
                "type": "color",
                "value": "#00ff00",
            },
        ],
    }
)


def test_open_pushes_a_loading_level_and_requests_a_describe():
    dialog = _FakeDialog()
    bridge = _fake_bridge()

    open_tool_settings_editor_in_palette(dialog, "fastkeyboardmouse", "Fast Keyboard Mouse", bridge)

    assert dialog.levels[0]["title"] == "Fast Keyboard Mouse: settings"
    assert dialog.levels[0]["entries"][0].title == "Loading settings…"
    bridge.describe_settings.assert_called_once_with("fastkeyboardmouse")


def test_snapshot_for_a_different_tool_is_ignored():
    dialog = _FakeDialog()
    bridge = _fake_bridge()
    open_tool_settings_editor_in_palette(dialog, "fastkeyboardmouse", "Fast Keyboard Mouse", bridge)

    other_tool = ToolSettings.from_dict({"tool_id": "other", "settings": []})
    bridge.settings_received.emit(other_tool)

    assert dialog.refreshed == []  # never touched -- not this editor's tool


def test_snapshot_refreshes_the_list_with_one_row_per_setting():
    dialog = _FakeDialog()
    bridge = _fake_bridge()
    open_tool_settings_editor_in_palette(dialog, "fastkeyboardmouse", "Fast Keyboard Mouse", bridge)

    bridge.settings_received.emit(SNAPSHOT)

    titles = [entry.title for entry in dialog.current_entries()]
    assert titles == [
        "Toggle mouse mode: alt+q",
        "Cursor speed: 5",
        "Dark mode: On",
        "Speed boost key: Shift",
        "Indicator color: #00ff00",
    ]


def _open_and_load(dialog=None, bridge=None):
    dialog = dialog or _FakeDialog()
    bridge = bridge or _fake_bridge()
    open_tool_settings_editor_in_palette(dialog, "fastkeyboardmouse", "Fast Keyboard Mouse", bridge)
    bridge.settings_received.emit(SNAPSHOT)
    return dialog, bridge


def _pick(dialog, setting_id):
    on_choose = dialog.root_on_choose()
    entry = next(e for e in dialog.current_entries() if e.payload == setting_id)
    on_choose(entry)


def test_picking_a_shortcut_row_opens_chord_capture():
    dialog, _bridge = _open_and_load()

    _pick(dialog, "ToggleKey")

    assert len(dialog.captures) == 1
    assert dialog.captures[0]["title"] == "Toggle mouse mode: press a shortcut"


def test_confirming_a_captured_chord_applies_it():
    dialog, bridge = _open_and_load()
    _pick(dialog, "ToggleKey")

    dialog.captures[0]["on_chord"]("ctrl+alt+q")

    bridge.set_setting.assert_called_once_with("fastkeyboardmouse", "ToggleKey", "ctrl+alt+q")


def test_picking_an_int_row_pushes_a_bounded_value_list():
    dialog, _bridge = _open_and_load()

    _pick(dialog, "BaseSpeed")

    value_level = dialog.levels[-1]
    assert [e.payload for e in value_level["entries"]] == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert [e.selected for e in value_level["entries"]] == [v == 5 for v in range(1, 11)]


def test_choosing_an_int_value_pops_then_applies():
    dialog, bridge = _open_and_load()
    _pick(dialog, "BaseSpeed")
    value_level = dialog.levels[-1]
    chosen_entry = next(e for e in value_level["entries"] if e.payload == 8)

    value_level["on_choose"](chosen_entry)

    assert dialog.pop_count == 1
    bridge.set_setting.assert_called_once_with("fastkeyboardmouse", "BaseSpeed", 8)


def test_picking_a_bool_row_offers_on_off():
    dialog, _bridge = _open_and_load()

    _pick(dialog, "DarkMode")

    value_level = dialog.levels[-1]
    assert [e.title for e in value_level["entries"]] == ["On", "Off"]
    assert [e.selected for e in value_level["entries"]] == [True, False]


def test_picking_an_enum_row_offers_its_choices():
    dialog, _bridge = _open_and_load()

    _pick(dialog, "SpeedModifier")

    value_level = dialog.levels[-1]
    assert [e.title for e in value_level["entries"]] == ["Shift", "Ctrl", "Alt"]
    assert [e.selected for e in value_level["entries"]] == [True, False, False]


def test_picking_a_color_row_opens_native_picker_and_applies_on_pick():
    dialog, bridge = _open_and_load()
    fake_color = MagicMock()
    fake_color.isValid.return_value = True
    fake_color.name.return_value = "#123456"

    with patch("core.tool_settings_editor.QColorDialog.getColor", return_value=fake_color):
        _pick(dialog, "IndicatorColor")

    bridge.set_setting.assert_called_once_with("fastkeyboardmouse", "IndicatorColor", "#123456")


def test_cancelling_the_color_picker_applies_nothing():
    dialog, bridge = _open_and_load()
    fake_color = MagicMock()
    fake_color.isValid.return_value = False

    with patch("core.tool_settings_editor.QColorDialog.getColor", return_value=fake_color):
        _pick(dialog, "IndicatorColor")

    bridge.set_setting.assert_not_called()


def test_a_fresh_snapshot_after_set_refreshes_with_the_new_value():
    dialog, bridge = _open_and_load()
    _pick(dialog, "BaseSpeed")
    value_level = dialog.levels[-1]
    chosen_entry = next(e for e in value_level["entries"] if e.payload == 8)
    value_level["on_choose"](chosen_entry)

    updated = ToolSettings.from_dict(
        {
            "tool_id": "fastkeyboardmouse",
            "settings": [{"id": "BaseSpeed", "label": "Cursor speed", "type": "int", "value": 8}],
        }
    )
    bridge.settings_received.emit(updated)

    titles = [entry.title for entry in dialog.current_entries()]
    assert titles == ["Cursor speed: 8"]


def test_picking_a_placeholder_row_before_any_snapshot_is_a_no_op():
    dialog = _FakeDialog()
    bridge = _fake_bridge()
    open_tool_settings_editor_in_palette(dialog, "fastkeyboardmouse", "Fast Keyboard Mouse", bridge)

    dialog.root_on_choose()(dialog.levels[0]["entries"][0])  # the "Loading…" row

    bridge.set_setting.assert_not_called()
