"""Detects whether a chord is already registered globally by some *other*
process. Windows hotkeys are exclusive system-wide (first ``RegisterHotKey``
caller wins) and there is no API to ask who owns one -- probing (register,
check ``GetLastError``, unregister) is the only way to find out. See
``core/hotkey_manager.py``'s ``apply()`` for where this gets used.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass

ERROR_HOTKEY_ALREADY_REGISTERED = 1409
# Arbitrary; only meaningful within this probe's own register/unregister pair,
# never left registered afterwards.
_PROBE_ID = 0xFCC1


@dataclass(frozen=True)
class HotkeyConflict:
    """A chord bound to ``command_id`` in our own keymap, but owned by another
    process at the OS level -- it will never actually fire."""

    chord: str
    command_id: str


def is_taken_by_other_process(modifiers: int, vk_code: int) -> bool:
    """Whether some other process already holds this exact (modifiers, vk)
    combination globally.

    Attempts the same ``RegisterHotKey`` call the real registration will make,
    against a throwaway NULL-hwnd registration owned only by this probe, then
    immediately releases it. ``modifiers`` should include whatever bits the
    real registration uses (e.g. winhotkeys' ``MOD_NOREPEAT``) so the probe
    tests the exact combination, not an approximation of it.
    """
    user32 = ctypes.windll.user32
    ctypes.windll.kernel32.SetLastError(0)
    ok = user32.RegisterHotKey(None, _PROBE_ID, modifiers, vk_code)
    if ok:
        user32.UnregisterHotKey(None, _PROBE_ID)
        return False
    return ctypes.GetLastError() == ERROR_HOTKEY_ALREADY_REGISTERED
