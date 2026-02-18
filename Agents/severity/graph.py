"""
graph.py

Builds and configures LangGraph workflow for Severity Agent.

Workflow:
    severity_llm_node
        ↓
    severity_calculation_node

Graph responsibilities:
- Define node execution order
- Manage shared SeverityState
- Return final evaluated severity result
"""

from langgraph.graph import StateGraph
from .state import SeverityState
from .nodes import severity_classification_node, severity_calculation_node

# Constructs and compiles the severity evaluation graph

def build_graph():
    builder = StateGraph(SeverityState)

    builder.add_node("classification_node", severity_classification_node)
    builder.add_node("calculation_node", severity_calculation_node)

    builder.set_entry_point("classification_node")
    builder.add_edge("classification_node", "calculation_node")

    builder.set_finish_point("calculation_node")

    return builder.compile()
