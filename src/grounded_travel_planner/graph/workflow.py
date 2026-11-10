"""Compile the bounded Coordinator, Planner, shared-tool and Chat workflow."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from grounded_travel_planner.agents.chat import ChatAgent
from grounded_travel_planner.agents.coordinator import CoordinatorAgent
from grounded_travel_planner.agents.planner import PlannerAgent
from grounded_travel_planner.config import RuntimeConfig
from grounded_travel_planner.graph.nodes import GraphNodes
from grounded_travel_planner.graph.state import PlannerState
from grounded_travel_planner.providers import PlaceSearchProvider, TraceSink


def build_travel_planner_graph(
    coordinator: CoordinatorAgent,
    planner: PlannerAgent,
    chat: ChatAgent,
    search: PlaceSearchProvider,
    trace_sink: TraceSink,
    config: RuntimeConfig,
):
    nodes = GraphNodes(coordinator, planner, chat, search, trace_sink, config)
    builder = StateGraph(PlannerState)
    builder.add_node("coordinator_route", nodes.coordinator_route)
    builder.add_node("planner_prepare", nodes.planner_prepare)
    builder.add_node("tavily_tool", nodes.tavily_tool)
    builder.add_node("planner_delegate", nodes.planner_delegate)
    builder.add_node("validate_candidate", nodes.validate_candidate)
    builder.add_node("chat_respond", nodes.chat_respond)
    builder.add_edge(START, "coordinator_route")

    def after_coordinator(state: PlannerState) -> str:
        decision = state.get("decision")
        if state.get("validation_issues") or not (
            decision and decision.requires_planner
        ):
            return "chat_respond"
        return "planner_prepare"

    def after_prepare(state: PlannerState) -> str:
        return "tavily_tool" if state.get("search_request") else "planner_delegate"

    def after_tool(state: PlannerState) -> str:
        if state.get("last_search_owner") == "chat":
            return "chat_respond"
        return "chat_respond" if state.get("validation_issues") else "planner_delegate"

    def after_planner(state: PlannerState) -> str:
        return (
            "chat_respond" if state.get("validation_issues") else "validate_candidate"
        )

    def after_chat(state: PlannerState) -> str:
        return "tavily_tool" if state.get("search_request") else END

    builder.add_conditional_edges(
        "coordinator_route",
        after_coordinator,
        {"planner_prepare": "planner_prepare", "chat_respond": "chat_respond"},
    )
    builder.add_conditional_edges(
        "planner_prepare",
        after_prepare,
        {"tavily_tool": "tavily_tool", "planner_delegate": "planner_delegate"},
    )
    builder.add_conditional_edges(
        "tavily_tool",
        after_tool,
        {"planner_delegate": "planner_delegate", "chat_respond": "chat_respond"},
    )
    builder.add_conditional_edges(
        "planner_delegate",
        after_planner,
        {"validate_candidate": "validate_candidate", "chat_respond": "chat_respond"},
    )
    builder.add_edge("validate_candidate", "chat_respond")
    builder.add_conditional_edges(
        "chat_respond", after_chat, {"tavily_tool": "tavily_tool", END: END}
    )
    return builder.compile()
