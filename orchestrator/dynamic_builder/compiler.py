import asyncio
import time
from typing import TypedDict, Annotated, Any, Dict
import operator
from langgraph.graph import StateGraph, START, END

# Universal Pipeline State
class DynamicState(TypedDict):
    raw_input: str
    results: Annotated[dict, operator.ior]  # Merges dictionaries

# Mock Agents for Demonstration
async def dummy_a1(state: DynamicState):
    await asyncio.sleep(1.5)
    return {"results": {"A1_similar_cases_agent": "Found 3 similar cases."}}

async def dummy_a2(state: DynamicState):
    await asyncio.sleep(2)
    return {"results": {"A2_pattern_agent": "High frequency pattern detected."}}

async def dummy_a3(state: DynamicState):
    await asyncio.sleep(1)
    return {"results": {"A3_severity_agent": "Severity is HIGH."}}

async def dummy_a4(state: DynamicState):
    await asyncio.sleep(1)
    return {"results": {"A4_occurrence_agent": "Occurrence score is 4."}}

async def dummy_a5(state: DynamicState):
    await asyncio.sleep(1.5)
    return {"results": {"A5_detection_agent": "Detection rate is 80%."}}

async def dummy_a6(state: DynamicState):
    await asyncio.sleep(1)
    return {"results": {"A6_regulatory_agent": "Reportable to FDA."}}

async def dummy_a7(state: DynamicState):
    await asyncio.sleep(2.5)
    return {"results": {"A7_reasoning_agent": "Final Reasoning: Based on all prior steps, CAPA is justified."}}

# Map frontend node IDs to these functions
AGENT_REGISTRY = {
    "A1_similar_cases_agent": dummy_a1,
    "A2_pattern_agent": dummy_a2,
    "A3_severity_agent": dummy_a3,
    "A4_occurrence_agent": dummy_a4,
    "A5_detection_agent": dummy_a5,
    "A6_regulatory_agent": dummy_a6,
    "A7_reasoning_agent": dummy_a7,
}

def build_dynamic_graph(nodes_data, edges_data):
    """
    Compiles a LangGraph exactly matching the UI's React Flow structure.
    nodes_data: list of dicts from UI (e.g. [{"id": "xyz", "data": {"id": "A1_..."}}])
    edges_data: list of dicts from UI (e.g. [{"source": "xyz", "target": "abc"}])
    """
    builder = StateGraph(DynamicState)
    added_node_ids = set()

    # 1. Add requested nodes
    for n in nodes_data:
        uid = n["id"]
        agent_type = n.get("data", {}).get("id")
        
        if agent_type in AGENT_REGISTRY:
            # We add the node using the unique React Flow ID as the node name!
            builder.add_node(uid, AGENT_REGISTRY[agent_type])
            added_node_ids.add(uid)

    if not added_node_ids:
        return None

    # 2. Add requested edges
    in_degrees = {nid: 0 for nid in added_node_ids}
    out_degrees = {nid: 0 for nid in added_node_ids}

    for e in edges_data:
        src = e["source"]
        dst = e["target"]
        if src in added_node_ids and dst in added_node_ids:
            builder.add_edge(src, dst)
            in_degrees[dst] += 1
            out_degrees[src] += 1

    # 3. Connect START to nodes with no incoming edges
    start_nodes = [nid for nid, deg in in_degrees.items() if deg == 0]
    for sn in start_nodes:
        builder.add_edge(START, sn)

    # 4. Connect nodes with no outgoing edges to END
    end_nodes = [nid for nid, deg in out_degrees.items() if deg == 0]
    for en in end_nodes:
        builder.add_edge(en, END)

    # Compile and return
    return builder.compile()
