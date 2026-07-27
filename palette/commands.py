"""The palette's command list.

Appearance is tuned from *here* — the palette itself — not the Settings
dialog; each Appearance command is navigable (drills into a submenu of
values in the same palette window, see ``CommandPalette.open``/
``push_level`` in the ``command_palette`` library) and persists its choice
via ``apply_appearance`` so the change is live immediately. Every command
below (including ``open_palette``, the opener itself) is a bindable global
OS hotkey target.

``settings`` is likewise navigable: picking it *inside* an open palette
drills into the full "Configure keyboard shortcuts" editor in the same
window (``mount_shortcuts`` -> ``open_shortcut_editor_in_palette``), never
opening a second window. It also keeps a plain ``run`` (``open_settings``)
for the case where a user has bound a global OS hotkey directly to
"settings" -- that path fires with no palette open yet, so it opens the
palette navigated straight to the editor instead of calling ``on_navigate``
against a dialog that doesn't exist.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from command_palette import Command, ListEntry, PaletteConfig
from command_palette.appearance import (
    HEIGHT_PCT_MAX,
    HEIGHT_PCT_MIN,
    OPACITY_PCT_MAX,
    OPACITY_PCT_MIN,
    WIDTH_PCT_MAX,
    WIDTH_PCT_MIN,
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog, QFileDialog

from config.settings_store import SettingsStore

if TYPE_CHECKING:
    from command_palette.dialog import FilterListDialog

_FONT_SIZES = [0, 10, 12, 14, 16, 18, 20, 24, 28, 32, 36, 40]
_PERCENT_STEP = 10
_RESET_TO_DEFAULT = "__reset__"
_CHOOSE_CUSTOM = "__custom__"
_ADD_TOOL_FOLDER = "__add_tool_folder__"

ApplyAppearance = Callable[[PaletteConfig], None]
_NO_RUN: Callable[[], None] = lambda: None  # noqa: E731 — navigable commands never run() directly


@dataclass(frozen=True)
class PaletteWiring:
    """Everything build_commands() needs from its host app, bundled instead of
    passed as a loose swarm of callbacks."""

    open_palette: Callable[[], None]
    open_settings: Callable[[], None]
    mount_shortcuts: Callable[[FilterListDialog], None]
    quit_app: Callable[[], None]
    settings_store: SettingsStore
    apply_appearance: ApplyAppearance
    refresh_tool_commands: Callable[[], None]


def build_commands(wiring: PaletteWiring) -> list[Command]:
    settings_store = wiring.settings_store
    apply_appearance = wiring.apply_appearance
    return [
        Command(
            command_id="open_palette",
            title="Open command palette",
            run=wiring.open_palette,
        ),
        Command(
            command_id="settings",
            title="Configure keyboard shortcuts",
            run=wiring.open_settings,
            on_navigate=wiring.mount_shortcuts,
        ),
        Command(
            command_id="appearance_font",
            title="Appearance: font size",
            run=_NO_RUN,
            submenu=lambda: _font_size_entries(settings_store.get_appearance().font_pt),
            on_submenu_choice=lambda value: apply_appearance(
                replace(settings_store.get_appearance(), font_pt=value)
            ),
        ),
        Command(
            command_id="appearance_width",
            title="Appearance: window width",
            run=_NO_RUN,
            submenu=lambda: _percent_entries(
                WIDTH_PCT_MIN, WIDTH_PCT_MAX, settings_store.get_appearance().width_pct
            ),
            on_submenu_choice=lambda value: apply_appearance(
                replace(settings_store.get_appearance(), width_pct=value)
            ),
        ),
        Command(
            command_id="appearance_height",
            title="Appearance: window height",
            run=_NO_RUN,
            submenu=lambda: _percent_entries(
                HEIGHT_PCT_MIN, HEIGHT_PCT_MAX, settings_store.get_appearance().height_pct
            ),
            on_submenu_choice=lambda value: apply_appearance(
                replace(settings_store.get_appearance(), height_pct=value)
            ),
        ),
        Command(
            command_id="appearance_opacity",
            title="Appearance: opacity",
            run=_NO_RUN,
            submenu=lambda: _percent_entries(
                OPACITY_PCT_MIN, OPACITY_PCT_MAX, settings_store.get_appearance().opacity_pct
            ),
            on_submenu_choice=lambda value: apply_appearance(
                replace(settings_store.get_appearance(), opacity_pct=value)
            ),
        ),
        Command(
            command_id="appearance_active_fg",
            title="Appearance: selected row color",
            run=_NO_RUN,
            submenu=_color_choice_entries,
            on_submenu_choice=lambda choice: _apply_active_color_choice(
                choice, settings_store, apply_appearance
            ),
        ),
        Command(
            command_id="appearance_inactive_fg",
            title="Appearance: other rows color",
            run=_NO_RUN,
            submenu=_color_choice_entries,
            on_submenu_choice=lambda choice: _apply_inactive_color_choice(
                choice, settings_store, apply_appearance
            ),
        ),
        Command(
            command_id="manage_tool_folders",
            title="Tools: manage folders",
            run=_NO_RUN,
            submenu=lambda: _tool_folder_entries(settings_store),
            on_submenu_choice=lambda choice: _apply_tool_folder_choice(
                choice, settings_store, wiring.refresh_tool_commands
            ),
        ),
        Command(command_id="quit", title="Quit FastCommandCenter", run=wiring.quit_app),
    ]


def _font_size_entries(current: int) -> list[ListEntry]:
    return [
        ListEntry(
            title=("Default (theme size)" if size == 0 else f"{size} pt"),
            payload=size,
            selected=size == current,
        )
        for size in _FONT_SIZES
    ]


def _percent_entries(minimum: int, maximum: int, current: int) -> list[ListEntry]:
    # ponytail: assumes [minimum, maximum] is step-aligned (true for all three
    # current bounds, 20-100); a future non-aligned bound would just drop the
    # top value from the list, not crash.
    return [
        ListEntry(title=f"{v}%", payload=v, selected=v == current)
        for v in range(minimum, maximum + 1, _PERCENT_STEP)
    ]


def _color_choice_entries() -> list[ListEntry]:
    return [
        ListEntry(title="Choose custom color…", payload=_CHOOSE_CUSTOM),
        ListEntry(title="Reset to theme default", payload=_RESET_TO_DEFAULT),
    ]


def _apply_active_color_choice(
    choice: str, settings_store: SettingsStore, apply_appearance: ApplyAppearance
) -> None:
    config = settings_store.get_appearance()
    if choice == _RESET_TO_DEFAULT:
        apply_appearance(replace(config, active_fg=None))
        return
    picked = _pick_native_color(config.active_fg, title="Selected row color")
    if picked is not None:
        apply_appearance(replace(config, active_fg=picked))


def _apply_inactive_color_choice(
    choice: str, settings_store: SettingsStore, apply_appearance: ApplyAppearance
) -> None:
    config = settings_store.get_appearance()
    if choice == _RESET_TO_DEFAULT:
        apply_appearance(replace(config, inactive_fg=None))
        return
    picked = _pick_native_color(config.inactive_fg, title="Other rows color")
    if picked is not None:
        apply_appearance(replace(config, inactive_fg=picked))


def _pick_native_color(initial: str | None, *, title: str) -> str | None:
    """Open the native color wheel (the one unavoidable exception to staying
    inside the palette — a color wheel can't be a filter-list)."""
    picked = QColorDialog.getColor(QColor(initial or "#ffffff"), None, title)
    return picked.name() if picked.isValid() else None


def _tool_folder_entries(settings_store: SettingsStore) -> list[ListEntry]:
    entries = [ListEntry(title="Add folder…", payload=_ADD_TOOL_FOLDER)]
    entries += [
        ListEntry(title=f"Remove: {folder}", payload=folder)
        for folder in settings_store.get_tool_dirs()
    ]
    return entries


def _apply_tool_folder_choice(
    choice: str, settings_store: SettingsStore, refresh_tool_commands: Callable[[], None]
) -> None:
    folders = settings_store.get_tool_dirs()
    if choice == _ADD_TOOL_FOLDER:
        picked = _pick_tool_folder()
        if picked is None or picked in folders:
            return
        settings_store.set_tool_dirs([*folders, picked])
    else:
        # Any other payload is one of the folders listed as a "Remove: ..."
        # row above -- selecting it removes it, symmetric with adding.
        settings_store.set_tool_dirs([folder for folder in folders if folder != choice])
    refresh_tool_commands()


def _pick_tool_folder() -> str | None:
    """Open the native folder browser (same "one unavoidable exception" as
    _pick_native_color — a filesystem path can't be a filter-list row)."""
    picked = QFileDialog.getExistingDirectory(None, "Add tool folder")
    return picked or None
