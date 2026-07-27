"""FCC adapter for protocol-v3 external text providers."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from uuid import uuid4

from command_palette import ListEntry
from command_palette.dialog import FilterListDialog
from fasttool_host import ToolBridge, ToolTextProviderDef, ToolTextResults
from PySide6.QtCore import QTimer

_LOADING = "Loading suggestions..."


class _ToolTextProviderEditor:
    def __init__(
        self,
        dialog: FilterListDialog,
        tool_id: str,
        provider: ToolTextProviderDef,
        bridge: ToolBridge,
        paste_text: Callable[[str], None],
    ) -> None:
        self._dialog = dialog
        self._tool_id = tool_id
        self._provider = provider
        self._bridge = bridge
        self._paste_text = paste_text
        self._session_id = uuid4().hex
        self._request_id = ""
        self._requested_query: str | None = None
        self._resolved_query: str | None = None
        self._rows: list[ListEntry] = []

    def open(self) -> None:
        self._bridge.text_results_received.connect(self._on_results)
        self._dialog.destroyed.connect(lambda: self._disconnect())
        self._dialog.push_level(
            [],
            self._choose,
            title=self._provider.label,
            placeholder="Search suggestions...",
            provider=self._provide,
            min_chars=self._provider.min_chars,
        )

    def _provide(self, query: str) -> list[ListEntry]:
        if query == self._resolved_query:
            return self._rows
        if query != self._requested_query:
            self._requested_query = query
            self._request_id = uuid4().hex
            self._bridge.query_text(
                self._tool_id,
                self._provider.id,
                self._session_id,
                self._request_id,
                query,
            )
        return [ListEntry(title=_LOADING)]

    def _on_results(self, results: ToolTextResults) -> None:
        if (
            results.tool_id != self._tool_id
            or results.provider_id != self._provider.id
            or results.session_id != self._session_id
            or results.request_id != self._request_id
        ):
            return
        self._resolved_query = self._requested_query
        self._rows = [
            ListEntry(title=item.title, subtitle=item.subtitle, payload=item.text)
            for item in results.results
        ]
        self._dialog.refresh_current_level([])

    def _choose(self, entry: ListEntry) -> None:
        if entry.payload is None:
            return
        text = str(entry.payload)
        self._disconnect()
        self._dialog.accept()
        QTimer.singleShot(100, lambda: self._paste_text(text))

    def _disconnect(self) -> None:
        with suppress(TypeError, RuntimeError):
            self._bridge.text_results_received.disconnect(self._on_results)


def open_tool_text_provider_in_palette(
    dialog: FilterListDialog,
    tool_id: str,
    provider: ToolTextProviderDef,
    bridge: ToolBridge,
    paste_text: Callable[[str], None],
) -> None:
    _ToolTextProviderEditor(dialog, tool_id, provider, bridge, paste_text).open()
