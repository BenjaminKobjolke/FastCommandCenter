"""Owns the live OS-global hotkey registrations, one per keymap binding.

Rewritten from a single-hotkey wrapper to multi: every command can now have
its own global chord (see ``config/settings_store.py``'s ``DEFAULT_BINDINGS``
and ``palette/commands.py``). ``winhotkeys.HotkeyManager`` (the underlying
class, not the single-hotkey ``HotkeyHandler`` convenience) already supports
registering many chords before one ``start_listening()`` call; a live edit is
teardown + rebuild, same as before, just over N registrations instead of one.
"""

from __future__ import annotations

from collections.abc import Callable

from command_palette.keymap import KeyMap
from winhotkeys import HotkeyManager as _WinHotkeyManager

from app_logger import AppLogger
from config.settings_store import normalize_chord


def winhotkeys_bindings(keymap: KeyMap) -> list[tuple[str, str]]:
    """Map a KeyMap's Qt-format chords to (winhotkeys chord, command_id) pairs."""
    return [(normalize_chord(chord), command_id) for chord, command_id in keymap.bindings]


class HotkeyManager:
    """Owns every live global hotkey registration; restarts all of them on any change."""

    def __init__(self) -> None:
        self._handle: _WinHotkeyManager | None = None

    def apply(self, keymap: KeyMap, on_fire: Callable[[str], None]) -> None:
        """Replace every live registration with ``keymap``'s bindings.

        ``on_fire`` is called with the fired binding's command id (on
        winhotkeys' background thread -- callers marshal to the GUI thread
        themselves, see ``core/hotkey_bridge.py``).
        """
        self.stop()
        handle = _WinHotkeyManager()
        for chord, command_id in winhotkeys_bindings(keymap):
            AppLogger.info(f"Registering global hotkey: {chord} -> {command_id}")
            handle.register_hotkey(chord, lambda cid=command_id: on_fire(cid), suppress=True)
        handle.start_listening()
        self._handle = handle

    def stop(self) -> None:
        """Stop listening; safe to call when nothing is registered."""
        if self._handle is not None:
            self._handle.stop_listening()
            self._handle = None

    def is_running(self) -> bool:
        """Whether any hotkeys are currently registered and listening."""
        return self._handle is not None
