"""In-palette editor for an external tool's OWN settings -- CONTRACT.md's
"Settings protocol (v2)": lists the tool's current settings (fetched live
over IPC, never read from its config file) and drills into a type-
appropriate editor per row. FastCommandCenter-specific (ties the library's
generic push_level/push_capture_level primitives to fasttool_host.ToolBridge)
so it lives here, not in python-command-palette -- same split as
`docs/EXTERNAL_TOOLS.md` draws for the rest of the tool-bridge integration.

Modeled on `command_palette.shortcut_editor_inline`'s `_LevelShortcutEditor`:
a class holding the live dialog + dependencies, with an `open()` entry point
and a top-level `open_tool_settings_editor_in_palette()` function mirroring
`open_shortcut_editor_in_palette`.
"""

from __future__ import annotations

from contextlib import suppress

from command_palette import ListEntry
from command_palette.dialog import FilterListDialog
from fasttool_host import ToolBridge, ToolSetting, ToolSettings
from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog

_DESCRIBE_TIMEOUT_MS = 3000
_NO_RESPONSE_TITLE = "Tool didn't respond -- is it running?"
_LOADING_TITLE = "Loading settings…"


def _display_value(setting: ToolSetting) -> str:
    if setting.type == "bool":
        return "On" if setting.value else "Off"
    return str(setting.value)


class _ToolSettingsEditor:
    """One in-progress "<tool>: settings" navigation. A fresh instance is
    created every time the command is chosen (see `core/tool_commands.py`),
    so there's nothing to reset between opens.

    Async note: `describe`/`set` replies arrive later, over IPC, not inline
    like the shortcut editor's synchronous KeymapState edits -- so the
    `bridge.settings_received` connection is made fresh per outstanding
    request and torn down as soon as it's used (see `_await_snapshot`),
    bounding a late/lost reply to at most one stale refresh rather than an
    ever-growing list of listeners. There is no hook in `FilterListDialog`
    for "the user navigated away" to cancel a request outright -- accepted
    as a known, narrow race for this v1.
    """

    def __init__(
        self, dialog: FilterListDialog, tool_id: str, tool_name: str, bridge: ToolBridge
    ) -> None:
        self._dialog = dialog
        self._tool_id = tool_id
        self._tool_name = tool_name
        self._bridge = bridge
        self._settings: dict[str, ToolSetting] = {}

    def open(self) -> None:
        # `on_choose` is fixed for the life of a pushed level -- refreshing
        # the entries later (once the snapshot arrives) does not change it
        # (see `FilterListDialog.refresh_current_level`) -- so `self._choose`
        # is wired up front, not a placeholder swapped in later. It's a safe
        # no-op against the loading/no-response rows below: their `payload`
        # is `None` by default, which never matches a real setting id.
        self._dialog.push_level(
            [ListEntry(title=_LOADING_TITLE)],
            self._choose,
            title=f"{self._tool_name}: settings",
        )
        self._await_snapshot()
        self._bridge.describe_settings(self._tool_id)

    # --- one outstanding describe/set -> snapshot round trip ---------------

    def _await_snapshot(self) -> None:
        self._bridge.settings_received.connect(self._on_snapshot)
        QTimer.singleShot(_DESCRIBE_TIMEOUT_MS, self._on_timeout)

    def _on_snapshot(self, settings: ToolSettings) -> None:
        if settings.tool_id != self._tool_id:
            return  # some other tool's reply -- not for this open editor
        self._disconnect_snapshot()
        self._settings = {setting.id: setting for setting in settings.settings}
        self._dialog.refresh_current_level(self._rows())

    def _on_timeout(self) -> None:
        if self._settings:
            return  # a reply already arrived; this timeout is moot
        self._disconnect_snapshot()
        self._dialog.refresh_current_level([ListEntry(title=_NO_RESPONSE_TITLE)])

    def _disconnect_snapshot(self) -> None:
        with suppress(TypeError, RuntimeError):
            self._bridge.settings_received.disconnect(self._on_snapshot)

    def _rows(self) -> list[ListEntry]:
        return [
            ListEntry(title=f"{setting.label}: {_display_value(setting)}", payload=setting.id)
            for setting in self._settings.values()
        ]

    # --- picking a row -> the type-appropriate editor -----------------------

    def _choose(self, entry: ListEntry) -> None:
        # `entry.payload` is `None` for the loading/no-response placeholder
        # rows (never a real setting id) -- `.get` makes picking one a no-op
        # rather than a crash. An unrecognized `type` (a setting kind newer
        # than this app knows about) degrades the same way: shown, but
        # picking it does nothing rather than raising.
        setting = self._settings.get(entry.payload)
        if setting is None:
            return
        editor = _EDITORS.get(setting.type)
        if editor is None:
            return
        editor(self, setting)

    def _edit_shortcut(self, setting: ToolSetting) -> None:
        self._dialog.push_capture_level(
            lambda chord: self._apply(setting.id, chord),
            title=f"{setting.label}: press a shortcut",
            prompt="Press a shortcut…",
            detected_fmt="Detected: {chord} · Enter to confirm · Esc to cancel",
        )

    def _edit_int(self, setting: ToolSetting) -> None:
        step = setting.step or 1
        minimum = setting.min if setting.min is not None else setting.value
        maximum = setting.max if setting.max is not None else setting.value
        rows = [
            ListEntry(title=str(value), payload=value, selected=value == setting.value)
            for value in range(minimum, maximum + 1, step)
        ]
        self._push_value_level(setting, rows)

    def _edit_bool(self, setting: ToolSetting) -> None:
        rows = [
            ListEntry(title="On", payload=True, selected=setting.value is True),
            ListEntry(title="Off", payload=False, selected=setting.value is not True),
        ]
        self._push_value_level(setting, rows)

    def _edit_enum(self, setting: ToolSetting) -> None:
        rows = [
            ListEntry(title=choice, payload=choice, selected=choice == setting.value)
            for choice in setting.choices or ()
        ]
        self._push_value_level(setting, rows)

    def _edit_color(self, setting: ToolSetting) -> None:
        # The one unavoidable exception to staying inside the palette -- same
        # as `palette/commands.py`'s appearance color pickers; a color wheel
        # can't be a filter-list.
        picked = QColorDialog.getColor(QColor(setting.value or "#ffffff"), None, setting.label)
        if picked.isValid():
            self._apply(setting.id, picked.name())

    def _push_value_level(self, setting: ToolSetting, rows: list[ListEntry]) -> None:
        def on_choose(entry: ListEntry) -> None:
            # Pop back to the settings list BEFORE applying: the eventual
            # snapshot reply calls refresh_current_level, which targets
            # whatever level is current at that time -- it must be the
            # settings list, not this value-list level, by the time that
            # arrives (mirrors the shortcut editor's confirm levels, which
            # pop_level() before proceeding for the same reason).
            self._dialog.pop_level()
            self._apply(setting.id, entry.payload)

        self._dialog.push_level(rows, on_choose, title=setting.label)

    def _apply(self, setting_id: str, value: object) -> None:
        self._await_snapshot()
        self._bridge.set_setting(self._tool_id, setting_id, value)


_EDITORS = {
    "shortcut": _ToolSettingsEditor._edit_shortcut,
    "int": _ToolSettingsEditor._edit_int,
    "bool": _ToolSettingsEditor._edit_bool,
    "enum": _ToolSettingsEditor._edit_enum,
    "color": _ToolSettingsEditor._edit_color,
}


def open_tool_settings_editor_in_palette(
    dialog: FilterListDialog, tool_id: str, tool_name: str, bridge: ToolBridge
) -> None:
    """Mount the "<tool_name>: settings" editor onto an already-open
    `dialog` as a pushed level -- the settings-protocol counterpart to
    `command_palette.open_shortcut_editor_in_palette`. `bridge` must be the
    same `ToolBridge` used to build this tool's commands (see
    `core/tool_commands.py`)."""
    _ToolSettingsEditor(dialog, tool_id, tool_name, bridge).open()
