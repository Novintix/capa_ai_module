from typing import List
from langgraph.graph import StateGraph, END, START
from langgraph.constants import Send
from orchestrator_service.state import RiskAssessmentState
from orchestrator_service.nodes import (
    input_validator_node,
    orchestrator_brain_node,
    severity_worker,
    occurrence_worker,
    detection_worker,
    historical_pattern_worker,
    regulatory_impact_worker,
    orchestrator_monitor_node,
    synthesizer_brain_node
)


def route_to_workers(state: RiskAssessmentState) -> List[Send]:
    """
    Conditional edge logic for dynamic worker dispatch using Send API.
    """
    if state.get("workflow_status") == "halted":
        return []
    
    plan = state.get("execution_plan", {})
    workers_needed = plan.get("workers_needed", [])
    
    sends = []
    for worker in workers_needed:
        # Map worker names from plan to their respective graph nodes
        if worker in [
            "severity_worker", 
            "occurrence_worker", 
            "detection_worker", 
            "historical_pattern_worker", 
            "regulatory_impact_worker"
        ]:
            sends.append(Send(worker, state))
            
    return sends


def build_graph(checkpointer=None):
    builder = StateGraph(RiskAssessmentState)

    # 1. Validation & Planning
    builder.add_node("input_validator", input_validator_node)
    builder.add_node("orchestrator_brain", orchestrator_brain_node)
    
    # 2. Parallel Workers
    builder.add_node("severity_worker", severity_worker)
    builder.add_node("occurrence_worker", occurrence_worker)
    builder.add_node("detection_worker", detection_worker)
    builder.add_node("historical_pattern_worker", historical_pattern_worker)
    builder.add_node("regulatory_impact_worker", regulatory_impact_worker)
    
    # 3. Monitor & Synthesis
    builder.add_node("orchestrator_monitor", orchestrator_monitor_node)
    builder.add_node("synthesizer_brain", synthesizer_brain_node)

    # Edges
    builder.add_edge(START, "input_validator")
    builder.add_edge("input_validator", "orchestrator_brain")

    # Dynamic Dispatch (Fan-out)
    builder.add_conditional_edges(
        "orchestrator_brain",
        route_to_workers,
        [
            "severity_worker",
            "occurrence_worker",
            "detection_worker",
            "historical_pattern_worker",
            "regulatory_impact_worker"
        ]
    )

    # Fan-in to Monitor
    builder.add_edge("severity_worker", "orchestrator_monitor")
    builder.add_edge("occurrence_worker", "orchestrator_monitor")
    builder.add_edge("detection_worker", "orchestrator_monitor")
    builder.add_edge("historical_pattern_worker", "orchestrator_monitor")
    builder.add_edge("regulatory_impact_worker", "orchestrator_monitor")

    # Synthesis (Monitor handles goto synthesizer_brain via Command)
    builder.add_edge("synthesizer_brain", END)

    return builder.compile(checkpointer=checkpointer)
