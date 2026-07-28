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
        self.accepted = 0

    def push_level(self, entries, on_choose, **kwargs):
        self.provider = kwargs["provider"]
        self.on_choose = on_choose

    def refresh_current_level(self, entries):
        self.refreshed += 1

    def accept(self):
        self.accepted += 1


class _Bridge:
    def __init__(self):
        self.text_results_received = _Signal()
        self.queries = []
        self.selections = []

    def query_text(self, *args):
        self.queries.append(args)

    def notify_text_selection(self, *args):
        self.selections.append(args)


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
    assert rows[0].payload.text == "a@example.com"


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


def test_choose_notifies_tool_of_selection_and_pastes_text(monkeypatch) -> None:
    import core.tool_text_provider as mod

    monkeypatch.setattr(mod.QTimer, "singleShot", staticmethod(lambda _ms, fn: fn()))
    dialog = _Dialog()
    bridge = _Bridge()
    pasted = []
    provider = ToolTextProviderDef("suggestions", "FastTextSuggester", 0)
    open_tool_text_provider_in_palette(dialog, "fasttextsuggester", provider, bridge, pasted.append)
    dialog.provider("mail")
    _, _, session_id, request_id, _ = bridge.queries[-1]
    bridge.text_results_received.emit(
        ToolTextResults(
            "fasttextsuggester",
            "suggestions",
            session_id,
            request_id,
            (ToolTextResult("email", "a@example.com", "personal"),),
        )
    )
    rows = dialog.provider("mail")

    dialog.on_choose(rows[0])

    assert bridge.selections == [
        (
            "fasttextsuggester",
            "suggestions",
            session_id,
            request_id,
            "email",
            "personal",
            "a@example.com",
        )
    ]
    assert pasted == ["a@example.com"]
    assert dialog.accepted == 1


def test_choose_on_loading_row_does_nothing() -> None:
    dialog = _Dialog()
    bridge = _Bridge()
    provider = ToolTextProviderDef("suggestions", "FastTextSuggester", 0)
    open_tool_text_provider_in_palette(
        dialog, "fasttextsuggester", provider, bridge, lambda _: None
    )
    loading = dialog.provider("mail")

    dialog.on_choose(loading[0])

    assert bridge.selections == []
    assert dialog.accepted == 0


def test_previous_rows_stay_visible_while_next_query_is_in_flight() -> None:
    dialog = _Dialog()
    bridge = _Bridge()
    provider = ToolTextProviderDef("suggestions", "FastTextSuggester", 0)
    open_tool_text_provider_in_palette(
        dialog, "fasttextsuggester", provider, bridge, lambda _: None
    )
    dialog.provider("a")
    _, _, session_id, request_id, _ = bridge.queries[-1]
    bridge.text_results_received.emit(
        ToolTextResults(
            "fasttextsuggester",
            "suggestions",
            session_id,
            request_id,
            (ToolTextResult("alpha", "alpha-text"),),
        )
    )

    in_flight = dialog.provider("ab")

    assert [row.title for row in in_flight] == ["alpha"]

    _, _, _, new_request, _ = bridge.queries[-1]
    bridge.text_results_received.emit(
        ToolTextResults(
            "fasttextsuggester",
            "suggestions",
            session_id,
            new_request,
            (ToolTextResult("abbey", "abbey-text"),),
        )
    )
    rows = dialog.provider("ab")

    assert [row.title for row in rows] == ["abbey"]
