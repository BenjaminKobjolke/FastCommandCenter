"""The palette's command list. v1 ships the plumbing (Settings, Quit); real
commands land here later."""

from __future__ import annotations

from collections.abc import Callable

from command_palette import Command


def build_commands(
    open_settings: Callable[[], None],
    quit_app: Callable[[], None],
) -> list[Command]:
    return [
        Command(
            command_id="settings",
            title="Settings: configure global shortcut",
            run=open_settings,
        ),
        Command(command_id="quit", title="Quit FastCommandCenter", run=quit_app),
    ]
