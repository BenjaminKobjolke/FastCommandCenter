"""Diagnostic for the settings protocol (v2, FastCommandCenter-tool-bridge/
CONTRACT.md): exercises ToolBridge.describe_settings() against a real tool,
bypassing the palette UI entirely, to tell apart "the wire protocol is
broken" from "something in the palette wiring is broken" -- see
docs/EXTERNAL_TOOLS.md's "Debugging the settings protocol" section for the
full playbook this is part of.

Usage (from this repo's root, tool NOT already running):

    uv run python tools/diag_settings.py "D:\\path\\to\\ToolFolder"

Prints each step (receiver window creation, manifest load, describe, the
resulting snapshot) and exits non-zero on the first failure, so it's obvious
which stage broke.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fasttool_host import ToolBridge, ToolSettings
from PySide6.QtCore import QCoreApplication, QTimer

_TIMEOUT_MS = 8000


def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: uv run python {Path(__file__).name} <tool-folder>")
        return 2
    tool_dir = Path(sys.argv[1])

    app = QCoreApplication(sys.argv)

    print("--- constructing ToolBridge ---")
    bridge = ToolBridge()
    if bridge._receiver.hwnd is None:
        print(
            "FAIL: SettingsReceiver never created its window (background thread "
            "never finished / crashed). This alone explains 'tool didn't respond' "
            "for every tool, not just one."
        )
        return 1
    print(f"OK: receiver window exists (hwnd={bridge._receiver.hwnd})")

    print(f"--- loading manifest from {tool_dir} ---")
    actions = bridge.load([tool_dir])
    manifests = bridge.manifests
    if not manifests:
        print("FAIL: no fasttool.json found/parsed in that folder.")
        return 1
    tool_id = manifests[0].id
    print(f"actions: {[a.command_id for a in actions]}")
    print(f"tool_id: {tool_id!r}")

    received: list[ToolSettings] = []
    bridge.settings_received.connect(received.append)

    print("--- calling describe_settings (launches the tool if not running) ---")
    bridge.describe_settings(tool_id)

    def check() -> None:
        if received:
            settings = received[0]
            count = len(settings.settings)
            print(f"OK: got snapshot for tool_id={settings.tool_id!r}, {count} settings")
            for s in settings.settings:
                print(f"  {s.id}: {s.type} = {s.value!r}")
            app.exit(0)

    poll = QTimer()
    poll.timeout.connect(check)
    poll.start(200)

    def on_timeout() -> None:
        if not received:
            print(
                f"FAIL: no snapshot within {_TIMEOUT_MS}ms -- tool never replied. "
                "If the tool is AHK-based, check its palette_debug.log (see "
                "docs/EXTERNAL_TOOLS.md) for where the round trip broke."
            )
            app.exit(1)

    QTimer.singleShot(_TIMEOUT_MS, on_timeout)

    code = app.exec()
    bridge.shutdown()
    return code


if __name__ == "__main__":
    sys.exit(main())
