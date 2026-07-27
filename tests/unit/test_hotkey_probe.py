"""``is_taken_by_other_process`` is exercised against the real win32
RegisterHotKey API (no way to fake OS-wide hotkey ownership), so this pins its
observable contract rather than mocking anything: a combination nothing else
holds reads as free, and one this test process itself has registered reads as
taken -- standing in for "some other process already owns it", since the API
that reports the conflict (``GetLastError() == 1409``) can't distinguish
"owned by someone else" from "owned by another registration on this thread".
"""

from __future__ import annotations

import ctypes

from core.hotkey_probe import _PROBE_ID, HotkeyConflict, is_taken_by_other_process

MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_ALT = 0x0001
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
VK_F24 = 0x87


def test_free_combination_is_not_taken():
    mods = MOD_CONTROL | MOD_SHIFT | MOD_ALT | MOD_WIN | MOD_NOREPEAT
    assert is_taken_by_other_process(mods, VK_F24) is False


def test_already_registered_combination_is_taken():
    mods = MOD_CONTROL | MOD_ALT | MOD_NOREPEAT
    user32 = ctypes.windll.user32
    other_id = _PROBE_ID + 1
    assert user32.RegisterHotKey(None, other_id, mods, VK_F24)
    try:
        assert is_taken_by_other_process(mods, VK_F24) is True
    finally:
        user32.UnregisterHotKey(None, other_id)


def test_probe_does_not_leave_its_own_registration_behind():
    mods = MOD_CONTROL | MOD_SHIFT | MOD_ALT | MOD_WIN | MOD_NOREPEAT
    is_taken_by_other_process(mods, VK_F24)
    # If the probe leaked its own registration, registering the same
    # combination again here would fail.
    user32 = ctypes.windll.user32
    assert user32.RegisterHotKey(None, _PROBE_ID, mods, VK_F24)
    user32.UnregisterHotKey(None, _PROBE_ID)


def test_hotkey_conflict_is_a_plain_typed_record():
    conflict = HotkeyConflict(chord="Meta+Shift+A", command_id="tool.example.toggle")
    assert conflict.chord == "Meta+Shift+A"
    assert conflict.command_id == "tool.example.toggle"
