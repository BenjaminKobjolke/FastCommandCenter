"""Characterization tests for the palette's command list: every command must be
findable by id so it can be a global-hotkey dispatch target and a shortcut-editor row.
"""

from dataclasses import replace

from command_palette import MemoryStore

from config.settings_store import SettingsStore
from palette.commands import PaletteWiring, build_commands


def _build_commands(
    *,
    open_palette=lambda: None,
    open_settings=lambda: None,
    mount_shortcuts=None,
    settings_store=None,
    refresh_tool_commands=lambda: None,
    paste_target_exe=lambda: None,
    open_paste_behaviour=lambda: None,
    apply_appearance=lambda _config: None,
):
    return build_commands(
        PaletteWiring(
            open_palette=open_palette,
            open_settings=open_settings,
            mount_shortcuts=mount_shortcuts or (lambda _dialog: None),
            quit_app=lambda: None,
            settings_store=settings_store or SettingsStore(MemoryStore()),
            apply_appearance=apply_appearance,
            refresh_tool_commands=refresh_tool_commands,
            paste_target_exe=paste_target_exe,
            open_paste_behaviour=open_paste_behaviour,
        )
    )


def test_open_palette_command_present_and_runnable():
    ran: list[str] = []
    commands = _build_commands(open_palette=lambda: ran.append("open_palette"))

    ids = [c.command_id for c in commands]
    assert "open_palette" in ids
    next(c for c in commands if c.command_id == "open_palette").run()
    assert ran == ["open_palette"]


def test_open_palette_is_hidden_from_the_main_list():
    # The palette is already open whenever its list shows, so "Open command
    # palette" is pointless as a row -- it stays bindable (hotkey dispatch and
    # the shortcut editor ignore is_enabled), but the dialog drops disabled
    # entries from the main list.
    from command_palette.entries import build_palette_entries
    from command_palette.keymap import KeyMap

    commands = _build_commands()
    open_cmd = next(c for c in commands if c.command_id == "open_palette")
    assert open_cmd.is_enabled() is False

    entries = build_palette_entries(commands, mru=[], keymap=KeyMap(bindings=()))
    visible = [e.payload.command_id for e in entries if e.enabled]
    assert "open_palette" not in visible


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
    assert "manage_tool_folders" in ids


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
    commands = _build_commands(settings_store=settings_store)
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
    commands = _build_commands(settings_store=settings_store)
    width_cmd = next(c for c in commands if c.command_id == "appearance_width")
    rows = width_cmd.submenu()
    assert [row.payload for row in rows if row.selected] == [60]


def test_choosing_a_font_size_applies_it_via_settings_store():
    applied = []
    commands = _build_commands(apply_appearance=lambda config: applied.append(config))
    font_cmd = next(c for c in commands if c.command_id == "appearance_font")
    font_cmd.on_submenu_choice(18)
    assert len(applied) == 1
    assert applied[0].font_pt == 18


def test_color_submenu_reset_choice_applies_none():
    applied = []
    commands = _build_commands(apply_appearance=lambda config: applied.append(config))
    active_fg_cmd = next(c for c in commands if c.command_id == "appearance_active_fg")
    rows = active_fg_cmd.submenu()
    reset_row = next(r for r in rows if r.title == "Reset to theme default")
    active_fg_cmd.on_submenu_choice(reset_row.payload)
    assert len(applied) == 1
    assert applied[0].active_fg is None


def test_manage_tool_folders_is_navigable_not_directly_runnable():
    commands = _build_commands()
    manage_cmd = next(c for c in commands if c.command_id == "manage_tool_folders")
    assert manage_cmd.submenu is not None
    assert manage_cmd.on_submenu_choice is not None


def test_tool_folder_submenu_always_offers_add_folder():
    commands = _build_commands()
    manage_cmd = next(c for c in commands if c.command_id == "manage_tool_folders")
    rows = manage_cmd.submenu()
    assert rows[0].title == "Add folder…"


def test_tool_folder_submenu_lists_configured_folders_as_removable_rows():
    settings_store = SettingsStore(MemoryStore())
    settings_store.set_tool_dirs(["D:/Tools/FastKeyboardMouse", "D:/Tools/FastWindowLayout"])
    commands = _build_commands(settings_store=settings_store)
    manage_cmd = next(c for c in commands if c.command_id == "manage_tool_folders")

    rows = manage_cmd.submenu()

    titles = [r.title for r in rows]
    assert "Remove: D:/Tools/FastKeyboardMouse" in titles
    assert "Remove: D:/Tools/FastWindowLayout" in titles


def test_choosing_an_existing_folder_removes_it_and_calls_refresh():
    settings_store = SettingsStore(MemoryStore())
    settings_store.set_tool_dirs(["D:/Tools/FastKeyboardMouse", "D:/Tools/FastWindowLayout"])
    refreshed = []
    commands = _build_commands(
        settings_store=settings_store, refresh_tool_commands=lambda: refreshed.append(True)
    )
    manage_cmd = next(c for c in commands if c.command_id == "manage_tool_folders")

    manage_cmd.on_submenu_choice("D:/Tools/FastKeyboardMouse")

    assert settings_store.get_tool_dirs() == ["D:/Tools/FastWindowLayout"]
    assert refreshed == [True]


def test_choosing_add_folder_with_no_pick_leaves_folders_unchanged(monkeypatch):
    import palette.commands as commands_module

    monkeypatch.setattr(commands_module, "_pick_tool_folder", lambda: None)
    settings_store = SettingsStore(MemoryStore())
    refreshed = []
    commands = _build_commands(
        settings_store=settings_store, refresh_tool_commands=lambda: refreshed.append(True)
    )
    manage_cmd = next(c for c in commands if c.command_id == "manage_tool_folders")

    manage_cmd.on_submenu_choice("__add_tool_folder__")

    assert settings_store.get_tool_dirs() == []
    assert refreshed == []


def test_paste_behaviour_submenu_shows_target_exe_with_current_chord_selected():
    settings_store = SettingsStore(MemoryStore())
    commands = _build_commands(
        settings_store=settings_store, paste_target_exe=lambda: "notepad.exe"
    )
    cmd = next(c for c in commands if c.command_id == "paste_behaviour")

    rows = cmd.submenu()

    assert [r.title for r in rows] == [
        "notepad.exe: Ctrl+V (default)",
        "notepad.exe: Ctrl+Shift+V",
        "notepad.exe: Ctrl+V, then Enter",
        "notepad.exe: Ctrl+Shift+V, then Enter",
    ]
    assert [r.payload for r in rows if r.selected] == ["ctrl+v"]


def test_paste_behaviour_submenu_preselects_a_stored_override():
    settings_store = SettingsStore(MemoryStore())
    settings_store.set_paste_overrides({"wezterm-gui.exe": "ctrl+shift+v"})
    commands = _build_commands(
        settings_store=settings_store, paste_target_exe=lambda: "wezterm-gui.exe"
    )
    cmd = next(c for c in commands if c.command_id == "paste_behaviour")

    rows = cmd.submenu()

    assert [r.payload for r in rows if r.selected] == ["ctrl+shift+v"]


def test_paste_behaviour_submenu_without_target_window_shows_placeholder_row():
    commands = _build_commands(paste_target_exe=lambda: None)
    cmd = next(c for c in commands if c.command_id == "paste_behaviour")

    rows = cmd.submenu()

    assert [r.title for r in rows] == ["No target window"]
    assert rows[0].payload is None


def test_paste_behaviour_choice_stores_an_override_for_the_target_exe():
    settings_store = SettingsStore(MemoryStore())
    commands = _build_commands(
        settings_store=settings_store, paste_target_exe=lambda: "notepad.exe"
    )
    cmd = next(c for c in commands if c.command_id == "paste_behaviour")

    cmd.on_submenu_choice("ctrl+shift+v")

    assert settings_store.get_paste_overrides()["notepad.exe"] == "ctrl+shift+v"


def test_paste_behaviour_choosing_default_removes_the_override():
    settings_store = SettingsStore(MemoryStore())
    settings_store.set_paste_overrides({"wezterm-gui.exe": "ctrl+shift+v"})
    commands = _build_commands(
        settings_store=settings_store, paste_target_exe=lambda: "wezterm-gui.exe"
    )
    cmd = next(c for c in commands if c.command_id == "paste_behaviour")

    cmd.on_submenu_choice("ctrl+v")

    assert "wezterm-gui.exe" not in settings_store.get_paste_overrides()


def test_paste_behaviour_submenu_preselects_a_stored_sequence():
    settings_store = SettingsStore(MemoryStore())
    settings_store.set_paste_overrides({"wezterm-gui.exe": "ctrl+shift+v,enter"})
    commands = _build_commands(
        settings_store=settings_store, paste_target_exe=lambda: "wezterm-gui.exe"
    )
    cmd = next(c for c in commands if c.command_id == "paste_behaviour")

    rows = cmd.submenu()

    assert [r.payload for r in rows if r.selected] == ["ctrl+shift+v,enter"]


def test_paste_behaviour_choice_stores_a_sequence():
    settings_store = SettingsStore(MemoryStore())
    commands = _build_commands(
        settings_store=settings_store, paste_target_exe=lambda: "notepad.exe"
    )
    cmd = next(c for c in commands if c.command_id == "paste_behaviour")

    cmd.on_submenu_choice("ctrl+v,enter")

    assert settings_store.get_paste_overrides()["notepad.exe"] == "ctrl+v,enter"


def test_paste_behaviour_choice_without_target_window_changes_nothing():
    settings_store = SettingsStore(MemoryStore())
    commands = _build_commands(settings_store=settings_store, paste_target_exe=lambda: None)
    cmd = next(c for c in commands if c.command_id == "paste_behaviour")

    cmd.on_submenu_choice(None)

    assert settings_store.get_paste_overrides() == {"wezterm-gui.exe": "ctrl+shift+v"}


def test_paste_behaviour_run_opens_the_palette_navigated_to_it():
    # A hotkey bound straight to "paste_behaviour" fires with no palette open
    # yet -- `run` must open the palette itself, navigated to the chord list
    # (same both-entry-paths rule as the settings command).
    ran: list[str] = []
    commands = _build_commands(open_paste_behaviour=lambda: ran.append("paste_behaviour"))

    next(c for c in commands if c.command_id == "paste_behaviour").run()

    assert ran == ["paste_behaviour"]


def test_choosing_add_folder_with_a_pick_appends_it(monkeypatch):
    import palette.commands as commands_module

    monkeypatch.setattr(commands_module, "_pick_tool_folder", lambda: "D:/Tools/NewTool")
    settings_store = SettingsStore(MemoryStore())
    refreshed = []
    commands = _build_commands(
        settings_store=settings_store, refresh_tool_commands=lambda: refreshed.append(True)
    )
    manage_cmd = next(c for c in commands if c.command_id == "manage_tool_folders")

    manage_cmd.on_submenu_choice("__add_tool_folder__")

    assert settings_store.get_tool_dirs() == ["D:/Tools/NewTool"]
    assert refreshed == [True]
