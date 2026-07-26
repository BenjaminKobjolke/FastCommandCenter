"""Characterization tests for the palette's command list: every command must be
findable by id so it can be a global-hotkey dispatch target and a shortcut-editor row.
"""

from dataclasses import replace

from command_palette import MemoryStore

from config.settings_store import SettingsStore
from palette.commands import build_commands


def _build_commands(*, open_palette=lambda: None, open_settings=lambda: None, mount_shortcuts=None):
    return build_commands(
        open_palette=open_palette,
        open_settings=open_settings,
        mount_shortcuts=mount_shortcuts or (lambda _dialog: None),
        quit_app=lambda: None,
        settings_store=SettingsStore(MemoryStore()),
        apply_appearance=lambda _config: None,
    )


def test_open_palette_command_present_and_runnable():
    ran: list[str] = []
    commands = _build_commands(open_palette=lambda: ran.append("open_palette"))

    ids = [c.command_id for c in commands]
    assert "open_palette" in ids
    next(c for c in commands if c.command_id == "open_palette").run()
    assert ran == ["open_palette"]


def test_settings_command_retitled_to_configure_shortcuts():
    commands = _build_commands()
    settings_cmd = next(c for c in commands if c.command_id == "settings")
    assert settings_cmd.title == "Configure keyboard shortcuts"


def test_settings_command_is_navigable_and_mounts_the_inline_editor():
    mounted: list[object] = []
    commands = _build_commands(mount_shortcuts=lambda dialog: mounted.append(dialog))

    settings_cmd = next(c for c in commands if c.command_id == "settings")
    assert settings_cmd.on_navigate is not None
    settings_cmd.on_navigate("fake-dialog")
    assert mounted == ["fake-dialog"]


def test_settings_command_run_still_works_for_a_direct_global_hotkey():
    # A hotkey bound straight to "settings" fires with no palette open yet,
    # so `run` (not `on_navigate`, which needs a live dialog) must still open
    # the palette itself, navigated to the editor.
    ran: list[str] = []
    commands = _build_commands(open_settings=lambda: ran.append("settings"))

    next(c for c in commands if c.command_id == "settings").run()
    assert ran == ["settings"]


def test_every_command_id_is_unique():
    ids = [c.command_id for c in _build_commands()]
    assert len(ids) == len(set(ids))


def test_quit_and_appearance_commands_still_present():
    ids = {c.command_id for c in _build_commands()}
    assert "quit" in ids
    assert "appearance_font" in ids
    assert "appearance_active_fg" in ids


def test_appearance_commands_are_navigable_not_directly_runnable():
    commands = _build_commands()
    appearance_ids = {
        "appearance_font",
        "appearance_width",
        "appearance_height",
        "appearance_opacity",
        "appearance_active_fg",
        "appearance_inactive_fg",
    }
    for command in commands:
        if command.command_id in appearance_ids:
            assert command.submenu is not None
            assert command.on_submenu_choice is not None


def test_font_size_submenu_rows_match_font_sizes():
    commands = _build_commands()
    font_cmd = next(c for c in commands if c.command_id == "appearance_font")
    rows = font_cmd.submenu()
    assert [row.payload for row in rows] == [0, 10, 12, 14, 16, 18, 20, 24, 28, 32, 36, 40]
    assert rows[0].title == "Default (theme size)"
    assert rows[1].title == "10 pt"


def test_font_size_submenu_preselects_the_current_value():
    settings_store = SettingsStore(MemoryStore())
    settings_store.set_appearance(replace(settings_store.get_appearance(), font_pt=18))
    commands = build_commands(
        open_palette=lambda: None,
        open_settings=lambda: None,
        mount_shortcuts=lambda _dialog: None,
        quit_app=lambda: None,
        settings_store=settings_store,
        apply_appearance=lambda _config: None,
    )
    font_cmd = next(c for c in commands if c.command_id == "appearance_font")
    rows = font_cmd.submenu()
    assert [row.payload for row in rows if row.selected] == [18]


def test_width_submenu_rows_match_percent_range():
    commands = _build_commands()
    width_cmd = next(c for c in commands if c.command_id == "appearance_width")
    rows = width_cmd.submenu()
    assert [row.payload for row in rows] == list(range(20, 101, 10))
    assert rows[0].title == "20%"


def test_width_submenu_preselects_the_current_value():
    settings_store = SettingsStore(MemoryStore())
    settings_store.set_appearance(replace(settings_store.get_appearance(), width_pct=60))
    commands = build_commands(
        open_palette=lambda: None,
        open_settings=lambda: None,
        mount_shortcuts=lambda _dialog: None,
        quit_app=lambda: None,
        settings_store=settings_store,
        apply_appearance=lambda _config: None,
    )
    width_cmd = next(c for c in commands if c.command_id == "appearance_width")
    rows = width_cmd.submenu()
    assert [row.payload for row in rows if row.selected] == [60]


def test_choosing_a_font_size_applies_it_via_settings_store():
    applied = []
    settings_store = SettingsStore(MemoryStore())
    commands = build_commands(
        open_palette=lambda: None,
        open_settings=lambda: None,
        mount_shortcuts=lambda _dialog: None,
        quit_app=lambda: None,
        settings_store=settings_store,
        apply_appearance=lambda config: applied.append(config),
    )
    font_cmd = next(c for c in commands if c.command_id == "appearance_font")
    font_cmd.on_submenu_choice(18)
    assert len(applied) == 1
    assert applied[0].font_pt == 18


def test_color_submenu_reset_choice_applies_none():
    applied = []
    settings_store = SettingsStore(MemoryStore())
    commands = build_commands(
        open_palette=lambda: None,
        open_settings=lambda: None,
        mount_shortcuts=lambda _dialog: None,
        quit_app=lambda: None,
        settings_store=settings_store,
        apply_appearance=lambda config: applied.append(config),
    )
    active_fg_cmd = next(c for c in commands if c.command_id == "appearance_active_fg")
    rows = active_fg_cmd.submenu()
    reset_row = next(r for r in rows if r.title == "Reset to theme default")
    active_fg_cmd.on_submenu_choice(reset_row.payload)
    assert len(applied) == 1
    assert applied[0].active_fg is None
