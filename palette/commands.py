"""The palette's command list.

Appearance is tuned from *here* — the palette itself — not the Settings
dialog; each Appearance command persists its choice and calls
``apply_appearance`` so the change is live on the very next open. Every
command below (including ``open_palette``, the opener itself) is a bindable
global OS hotkey target — see ``palette/commands.py``'s ``settings`` command,
which opens the shared library's shortcut editor, and ``core/hotkey_manager.py``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from command_palette import Command, PaletteConfig, pick_option
from command_palette.appearance import (
    HEIGHT_PCT_MAX,
    HEIGHT_PCT_MIN,
    OPACITY_PCT_MAX,
    OPACITY_PCT_MIN,
    WIDTH_PCT_MAX,
    WIDTH_PCT_MIN,
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog

from config.settings_store import SettingsStore

_FONT_SIZES = [0, 10, 12, 14, 16, 18, 20, 24, 28, 32, 36, 40]
_PERCENT_STEP = 10
_PICKER_PLACEHOLDER = "Type to filter…"
_RESET_TO_DEFAULT = "__reset__"
_CHOOSE_CUSTOM = "__custom__"

ApplyAppearance = Callable[[PaletteConfig], None]


def build_commands(
    open_palette: Callable[[], None],
    open_settings: Callable[[], None],
    quit_app: Callable[[], None],
    settings_store: SettingsStore,
    apply_appearance: ApplyAppearance,
) -> list[Command]:
    return [
        Command(
            command_id="open_palette",
            title="Open command palette",
            run=open_palette,
        ),
        Command(
            command_id="settings",
            title="Configure keyboard shortcuts",
            run=open_settings,
        ),
        Command(
            command_id="appearance_font",
            title="Appearance: font size",
            run=lambda: _pick_font_size(settings_store, apply_appearance),
        ),
        Command(
            command_id="appearance_width",
            title="Appearance: window width",
            run=lambda: _pick_width(settings_store, apply_appearance),
        ),
        Command(
            command_id="appearance_height",
            title="Appearance: window height",
            run=lambda: _pick_height(settings_store, apply_appearance),
        ),
        Command(
            command_id="appearance_opacity",
            title="Appearance: opacity",
            run=lambda: _pick_opacity(settings_store, apply_appearance),
        ),
        Command(
            command_id="appearance_active_fg",
            title="Appearance: selected row color",
            run=lambda: _pick_active_color(settings_store, apply_appearance),
        ),
        Command(
            command_id="appearance_inactive_fg",
            title="Appearance: other rows color",
            run=lambda: _pick_inactive_color(settings_store, apply_appearance),
        ),
        Command(command_id="quit", title="Quit FastCommandCenter", run=quit_app),
    ]


def _pick_font_size(settings_store: SettingsStore, apply_appearance: ApplyAppearance) -> None:
    labels = {size: ("Default (theme size)" if size == 0 else f"{size} pt") for size in _FONT_SIZES}
    chosen = pick_option(None, labels, title="Font size", placeholder=_PICKER_PLACEHOLDER)
    if chosen is not None:
        apply_appearance(replace(settings_store.get_appearance(), font_pt=chosen))


def _pick_width(settings_store: SettingsStore, apply_appearance: ApplyAppearance) -> None:
    chosen = _pick_percent("Window width (% of screen)", WIDTH_PCT_MIN, WIDTH_PCT_MAX)
    if chosen is not None:
        apply_appearance(replace(settings_store.get_appearance(), width_pct=chosen))


def _pick_height(settings_store: SettingsStore, apply_appearance: ApplyAppearance) -> None:
    chosen = _pick_percent("Window height (% of screen)", HEIGHT_PCT_MIN, HEIGHT_PCT_MAX)
    if chosen is not None:
        apply_appearance(replace(settings_store.get_appearance(), height_pct=chosen))


def _pick_opacity(settings_store: SettingsStore, apply_appearance: ApplyAppearance) -> None:
    chosen = _pick_percent("Opacity", OPACITY_PCT_MIN, OPACITY_PCT_MAX)
    if chosen is not None:
        apply_appearance(replace(settings_store.get_appearance(), opacity_pct=chosen))


def _pick_active_color(settings_store: SettingsStore, apply_appearance: ApplyAppearance) -> None:
    config = settings_store.get_appearance()
    changed, color = _pick_color(config.active_fg, title="Selected row color")
    if changed:
        apply_appearance(replace(config, active_fg=color))


def _pick_inactive_color(settings_store: SettingsStore, apply_appearance: ApplyAppearance) -> None:
    config = settings_store.get_appearance()
    changed, color = _pick_color(config.inactive_fg, title="Other rows color")
    if changed:
        apply_appearance(replace(config, inactive_fg=color))


def _pick_percent(title: str, minimum: int, maximum: int) -> int | None:
    # ponytail: assumes [minimum, maximum] is step-aligned (true for all three
    # current bounds, 20-100); a future non-aligned bound would just drop the
    # top value from the list, not crash.
    options = {v: f"{v}%" for v in range(minimum, maximum + 1, _PERCENT_STEP)}
    return pick_option(None, options, title=title, placeholder=_PICKER_PLACEHOLDER)


def _pick_color(initial: str | None, *, title: str) -> tuple[bool, str | None]:
    """Prompt to choose a custom color or reset to the theme default.

    Returns ``(changed, color)``; ``color`` is ``None`` for "reset to
    default". ``changed`` is ``False`` if the user backed out at any step.
    """
    choice = pick_option(
        None,
        {_CHOOSE_CUSTOM: "Choose custom color…", _RESET_TO_DEFAULT: "Reset to theme default"},
        title=title,
        placeholder=_PICKER_PLACEHOLDER,
    )
    if choice is None:
        return False, None
    if choice == _RESET_TO_DEFAULT:
        return True, None
    picked = QColorDialog.getColor(QColor(initial or "#ffffff"), None, title)
    if not picked.isValid():
        return False, None
    return True, picked.name()
