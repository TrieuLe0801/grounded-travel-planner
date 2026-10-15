"""Compile the bounded two-agent LangGraph workflow."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from grounded_travel_planner.agents.coordinator import CoordinatorAgent
from grounded_travel_planner.agents.planner import PlannerAgent
from grounded_travel_planner.config import RuntimeConfig
from grounded_travel_planner.graph.nodes import GraphNodes
from grounded_travel_planner.graph.state import PlannerState
from grounded_travel_planner.providers import TraceSink


def build_two_agent_graph(
    coordinator: CoordinatorAgent,
    planner: PlannerAgent,
    trace_sink: TraceSink,
    config: RuntimeConfig,
):
    nodes = GraphNodes(coordinator, planner, trace_sink, config)
    builder = StateGraph(PlannerState)
    builder.add_node("coordinator_classify", nodes.coordinator_classify)
    builder.add_node("validate_input", nodes.validate_input)
    builder.add_node("planner_delegate", nodes.planner_delegate)
    builder.add_node("validate_candidate", nodes.validate_candidate)
    builder.add_node("prepare_repair", nodes.prepare_repair)
    builder.add_node("finalize", nodes.finalize)

    builder.add_edge(START, "coordinator_classify")

    def after_classify(state: PlannerState) -> str:
        if state.get("validation_issues"):
            return "finalize"
        decision = state.get("decision")
        return (
            "validate_input" if decision and decision.requires_planner else "finalize"
        )

    def after_input(state: PlannerState) -> str:
        return "finalize" if state.get("validation_issues") else "planner_delegate"

    def after_planner(state: PlannerState) -> str:
        return "finalize" if state.get("validation_issues") else "validate_candidate"

    def after_candidate(state: PlannerState) -> str:
        if not state.get("validation_issues"):
            return "finalize"
        if state.get("repair_attempts", 0) < config.repair_attempt_limit:
            return "prepare_repair"
        return "finalize"

    builder.add_conditional_edges(
        "coordinator_classify",
        after_classify,
        {"validate_input": "validate_input", "finalize": "finalize"},
    )
    builder.add_conditional_edges(
        "validate_input",
        after_input,
        {"planner_delegate": "planner_delegate", "finalize": "finalize"},
    )
    builder.add_conditional_edges(
        "planner_delegate",
        after_planner,
        {"validate_candidate": "validate_candidate", "finalize": "finalize"},
    )
    builder.add_conditional_edges(
        "validate_candidate",
        after_candidate,
        {"prepare_repair": "prepare_repair", "finalize": "finalize"},
    )
    builder.add_edge("prepare_repair", "planner_delegate")
    builder.add_edge("finalize", END)
    return builder.compile()
