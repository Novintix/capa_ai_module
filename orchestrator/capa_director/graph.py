import redis
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.redis import RedisSaver
from .state import DirectorState
from .nodes import (
    risk_analysis_node,
    rca_node,
    action_plan_node,
    effectiveness_node,
    finalize_node,
    error_recovery_node,
)
from .routing import (
    route_after_risk,
    route_after_rca,
    route_after_action_plan,
    route_after_effectiveness,
)

from config.redis_config import redis_client

def build_director_graph(interrupt_for_human: bool = True):
    """
    TRUE CAPA Director Orchestrator (O1):
    """
    # Fix: Use keyword argument to avoid AttributeError string issues
    checkpointer = RedisSaver(redis_client=redis_client)
    
    workflow = StateGraph(DirectorState)

    # ── Nodes ─────────────────────────────────────────────────────────────────
    workflow.add_node("risk_analysis", risk_analysis_node)
    workflow.add_node("rca",           rca_node)
    workflow.add_node("action_plan",   action_plan_node)
    workflow.add_node("effectiveness", effectiveness_node)
    workflow.add_node("finalize",      finalize_node)
    workflow.add_node("error_recovery", error_recovery_node)

    # ── Entry ─────────────────────────────────────────────────────────────────
    workflow.set_entry_point("risk_analysis")

    # ── Conditional edges ─────────────────────────────────────────────────────
    workflow.add_conditional_edges(
        "risk_analysis",
        route_after_risk,
        {
            "rca":            "rca",
            "action_plan":    "action_plan",
            "error_recovery": "error_recovery",
        },
    )

    workflow.add_conditional_edges(
        "rca",
        route_after_rca,
        {
            "action_plan":    "action_plan",
            "error_recovery": "error_recovery",
        },
    )

    workflow.add_conditional_edges(
        "action_plan",
        route_after_action_plan,
        {
            "effectiveness":  "effectiveness",
            "error_recovery": "error_recovery",
        },
    )

    workflow.add_conditional_edges(
        "effectiveness",
        route_after_effectiveness,
        {
            "finalize":       "finalize",
            "error_recovery": "error_recovery",
        },
    )

    # Error recovery routes back to the failed node or finalize
    workflow.add_conditional_edges(
        "error_recovery",
        lambda state: state.get("recovery_next", "finalize"),
        {
            "risk_analysis": "risk_analysis",
            "rca":           "rca",
            "action_plan":   "action_plan",
            "effectiveness": "effectiveness",
            "finalize":      "finalize",
        },
    )

    workflow.add_edge("finalize", END)

    # ── Human-in-the-loop ─────────────────────────────────────────────────────
    # Graph pauses BEFORE these nodes; resume endpoint injects human_approved
    interrupt_nodes = ["rca", "action_plan", "effectiveness"] if interrupt_for_human else []

    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=interrupt_nodes,
    )