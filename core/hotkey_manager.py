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
from config.settings_store import _to_qt_chord, normalize_chord
from core.hotkey_probe import HotkeyConflict, is_taken_by_other_process


def winhotkeys_bindings(keymap: KeyMap) -> list[tuple[str, str]]:
    """Map a KeyMap's Qt-format chords to (winhotkeys chord, command_id) pairs."""
    return [(normalize_chord(chord), command_id) for chord, command_id in keymap.bindings]


class HotkeyManager:
    """Owns every live global hotkey registration; restarts all of them on any change."""

    def __init__(self) -> None:
        self._handle: _WinHotkeyManager | None = None

    def apply(self, keymap: KeyMap, on_fire: Callable[[str], None]) -> list[HotkeyConflict]:
        """Replace every live registration with ``keymap``'s bindings.

        ``on_fire`` is called with the fired binding's command id (on
        winhotkeys' background thread -- callers marshal to the GUI thread
        themselves, see ``core/hotkey_bridge.py``).

        Returns any chords already owned by another process -- winhotkeys
        registers on a background thread and silently logs+continues past a
        conflict (see its ``hotkey.py``), so without this a chord some other
        program already holds would bind here but simply never fire, with no
        signal to the user. Probed with ``self.stop()`` already run and before
        ``start_listening()`` re-registers for real, so our own prior bindings
        never show up as a false self-conflict.
        """
        self.stop()
        handle = _WinHotkeyManager()
        conflicts: list[HotkeyConflict] = []
        for chord, command_id in winhotkeys_bindings(keymap):
            AppLogger.info(f"Registering global hotkey: {chord} -> {command_id}")
            handle.register_hotkey(chord, lambda cid=command_id: on_fire(cid), suppress=True)
            # winhotkeys' own combination parser, reused so the probe tests the
            # exact modifier bitmask (incl. MOD_NOREPEAT) the real
            # registration below will use.
            modifiers, vk_code = handle._parse_hotkey_combination(chord)
            if vk_code is not None and is_taken_by_other_process(modifiers, vk_code):
                AppLogger.warning(
                    f"Hotkey already in use by another program: {chord} ({command_id})"
                )
                conflicts.append(HotkeyConflict(chord=_to_qt_chord(chord), command_id=command_id))
        handle.start_listening()
        self._handle = handle
        return conflicts

    def stop(self) -> None:
        """Stop listening; safe to call when nothing is registered."""
        if self._handle is not None:
            self._handle.stop_listening()
            self._handle = None

    def is_running(self) -> bool:
        """Whether any hotkeys are currently registered and listening."""
        return self._handle is not None
