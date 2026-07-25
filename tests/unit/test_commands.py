"""Characterization tests for the palette's command list: every command must be
findable by id so it can be a global-hotkey dispatch target and a shortcut-editor row.
"""

from command_palette import MemoryStore

from config.settings_store import SettingsStore
from palette.commands import build_commands


def _build_commands(*, open_palette=lambda: None):
    return build_commands(
        open_palette=open_palette,
        open_settings=lambda: None,
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


def test_every_command_id_is_unique():
    ids = [c.command_id for c in _build_commands()]
    assert len(ids) == len(set(ids))


def test_quit_and_appearance_commands_still_present():
    ids = {c.command_id for c in _build_commands()}
    assert "quit" in ids
    assert "appearance_font" in ids
    assert "appearance_active_fg" in ids
