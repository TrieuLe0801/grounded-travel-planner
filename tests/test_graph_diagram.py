"""Offline checks for the read-only compiled LangGraph architecture view."""

from __future__ import annotations

import base64
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from streamlit.testing.v1 import AppTest

from grounded_travel_planner.adapters import NoOpTraceSink
from grounded_travel_planner.agents import ChatAgent, CoordinatorAgent, PlannerAgent
from grounded_travel_planner.config import RuntimeConfig
from grounded_travel_planner.service import TravelPlannerService
from grounded_travel_planner.ui.graph_diagram import (
    DiagramEdge,
    DiagramNode,
    compiled_graph_svg,
    render_topology_svg,
    topology_from_compiled_graph,
)

PAGE_PATH = (
    Path(__file__).parents[1]
    / "src"
    / "grounded_travel_planner"
    / "ui"
    / "pages"
    / "2_Graph_Architecture.py"
)


class NoCallModel:
    """A provider double that proves diagram rendering never invokes a model."""

    model_name = "coordinator-test-model"

    def generate_structured(self, *args: Any, **kwargs: Mapping[str, Any]) -> Any:
        raise AssertionError("The graph inspection page must not invoke a model")


class NoCallSearch:
    """A provider double that proves diagram rendering never searches."""

    def search_places(self, *args: Any, **kwargs: Mapping[str, Any]) -> list[Any]:
        raise AssertionError("The graph inspection page must not call Tavily")


def _service() -> TravelPlannerService:
    config = RuntimeConfig()
    return TravelPlannerService(
        CoordinatorAgent(NoCallModel()),
        PlannerAgent(NoCallModel()),
        ChatAgent(NoCallModel()),
        search=NoCallSearch(),
        trace_sink=NoOpTraceSink(),
        config=config,
    )


def test_svg_copies_compiled_topology_including_repair_loop() -> None:
    service = _service()
    nodes, edges = topology_from_compiled_graph(service.graph)
    identifiers = {node.identifier for node in nodes}
    edge_pairs = {(edge.source, edge.target, edge.conditional) for edge in edges}
    svg = compiled_graph_svg(service.graph)

    assert {
        "__start__",
        "coordinator_route",
        "planner_prepare",
        "tavily_tool",
        "planner_delegate",
        "validate_candidate",
        "chat_respond",
        "__end__",
    } <= identifiers
    assert ("coordinator_route", "planner_prepare", True) in edge_pairs
    assert ("coordinator_route", "chat_respond", True) in edge_pairs
    assert ("planner_prepare", "tavily_tool", True) in edge_pairs
    assert ("tavily_tool", "planner_delegate", True) in edge_pairs
    assert ("tavily_tool", "chat_respond", True) in edge_pairs
    assert ("planner_delegate", "validate_candidate", True) in edge_pairs
    assert ("validate_candidate", "chat_respond", False) in edge_pairs
    assert ("chat_respond", "__end__", True) in edge_pairs
    assert "Coordinator" in svg
    assert "Chat" in svg
    assert "Tavily tool" in svg
    assert "stroke-dasharray" in svg


def test_service_get_graph_image_returns_png_and_optionally_writes_file(
    monkeypatch, tmp_path
) -> None:
    service = _service()
    expected = b"\x89PNG\r\n\x1a\nrendered"
    received_paths: list[str | None] = []

    class FakeRenderableGraph:
        def draw_mermaid_png(self, *, output_file_path=None):
            received_paths.append(output_file_path)
            return expected

    monkeypatch.setattr(
        service.graph, "get_graph", lambda *, xray=False: FakeRenderableGraph()
    )

    assert service.get_graph_image() == expected
    assert received_paths == [None]

    assert service.get_graph_image(tmp_path) == expected
    assert received_paths[-1] == str(tmp_path / "flow.png")


def test_svg_escapes_dynamic_graph_labels() -> None:
    svg = render_topology_svg(
        [
            DiagramNode(
                identifier="<unknown>",
                label="<script>alert(1)</script>",
                description="A & B < C",
                kind="boundary",
            )
        ],
        [DiagramEdge("<unknown>", "<unknown>", False)],
    )

    assert "<script>" not in svg
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in svg
    assert "A &amp; B &lt; C" in svg


def test_graph_page_renders_offline_without_changing_session_plan(
    monkeypatch,
) -> None:
    service = _service()
    graph_image = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
        "+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    monkeypatch.setattr(service, "get_graph_image", lambda: graph_image)
    monkeypatch.setattr(
        TravelPlannerService,
        "from_environment",
        classmethod(lambda cls: service),
    )
    app = AppTest.from_file(PAGE_PATH)
    sentinel = {"plan": "must remain session-owned"}
    app.session_state.current_plan = sentinel
    app.run(timeout=10)

    text = "\n".join(
        str(item.value)
        for collection in (app.title, app.caption, app.subheader, app.markdown)
        for item in collection
        if getattr(item, "value", "")
    )
    assert "Kiến trúc LangGraph" in text
    assert "không gọi model, Tavily hoặc LangSmith" in text
    assert app.session_state.current_plan == sentinel
    assert len(app.get("image")) == 1
    assert len(app.get("download_button")) == 1
    assert app.get("download_button")[0].label == "Tải ảnh graph PNG"
