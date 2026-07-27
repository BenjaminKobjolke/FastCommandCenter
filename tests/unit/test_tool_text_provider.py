from fasttool_host import ToolTextProviderDef, ToolTextResult, ToolTextResults

from core.tool_text_provider import open_tool_text_provider_in_palette


class _Signal:
    def __init__(self):
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)

    def disconnect(self, slot):
        self.slots.remove(slot)

    def emit(self, value):
        for slot in list(self.slots):
            slot(value)


class _Destroyed(_Signal):
    pass


class _Dialog:
    def __init__(self):
        self.destroyed = _Destroyed()
        self.provider = None
        self.on_choose = None
        self.refreshed = 0

    def push_level(self, entries, on_choose, **kwargs):
        self.provider = kwargs["provider"]
        self.on_choose = on_choose

    def refresh_current_level(self, entries):
        self.refreshed += 1


class _Bridge:
    def __init__(self):
        self.text_results_received = _Signal()
        self.queries = []

    def query_text(self, *args):
        self.queries.append(args)


def test_latest_correlated_results_replace_loading_row() -> None:
    dialog = _Dialog()
    bridge = _Bridge()
    provider = ToolTextProviderDef("suggestions", "FastTextSuggester", 0)
    open_tool_text_provider_in_palette(
        dialog, "fasttextsuggester", provider, bridge, lambda _: None
    )

    loading = dialog.provider("mail")
    _, _, session_id, request_id, _ = bridge.queries[-1]
    bridge.text_results_received.emit(
        ToolTextResults(
            "fasttextsuggester",
            "suggestions",
            session_id,
            request_id,
            (ToolTextResult("email", "a@example.com"),),
        )
    )
    rows = dialog.provider("mail")

    assert loading[0].title == "Loading suggestions..."
    assert rows[0].title == "email"
    assert rows[0].payload == "a@example.com"


def test_stale_request_results_are_ignored() -> None:
    dialog = _Dialog()
    bridge = _Bridge()
    provider = ToolTextProviderDef("suggestions", "FastTextSuggester", 0)
    open_tool_text_provider_in_palette(
        dialog, "fasttextsuggester", provider, bridge, lambda _: None
    )
    dialog.provider("first")
    _, _, session_id, old_request, _ = bridge.queries[-1]
    dialog.provider("second")

    bridge.text_results_received.emit(
        ToolTextResults(
            "fasttextsuggester",
            "suggestions",
            session_id,
            old_request,
            (ToolTextResult("stale", "stale"),),
        )
    )

    assert dialog.refreshed == 0
