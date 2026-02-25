from typing import Literal, List
from langgraph.graph import StateGraph, END, START
from orchestrator_service.state import RiskAssessmentState
from orchestrator_service.nodes import (
    input_validation_node,
    severity_node,
    occurrence_node,
    detection_node,
    aggregation_node,
    conflict_detection_node
)

def route_input_validation(state: RiskAssessmentState) -> List[str]:
    if state.get("workflow_status") == "halted":
        return [END]
    return ["severity", "occurrence", "detection"]


def route_conflict(state: RiskAssessmentState) -> Literal["aggregation", "__end__"]:
    if state.get("workflow_status") == "escalated":
        return END
    return "aggregation"


def build_graph(checkpointer=None):
    builder = StateGraph(RiskAssessmentState)

    # Add Nodes
    builder.add_node("input_validation", input_validation_node)
    builder.add_node("severity", severity_node)
    builder.add_node("occurrence", occurrence_node)
    builder.add_node("detection", detection_node)
    builder.add_node("conflict_detection", conflict_detection_node)
    builder.add_node("aggregation", aggregation_node)

    # Edges
    builder.add_edge(START, "input_validation")

    # Fan-out to parallel agents
    builder.add_conditional_edges(
        "input_validation",
        route_input_validation,
        {
            "severity": "severity",
            "occurrence": "occurrence",
            "detection": "detection",
            END: END
        }
    )

    # Fan-in to conflict detection
    builder.add_edge("severity", "conflict_detection")
    builder.add_edge("occurrence", "conflict_detection")
    builder.add_edge("detection", "conflict_detection")

    builder.add_conditional_edges(
        "conflict_detection",
        route_conflict
    )

    builder.add_edge("aggregation", END)

    return builder.compile(checkpointer=checkpointer)
