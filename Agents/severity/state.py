"""
state.py

Defines the SeverityState used in the LangGraph workflow.

This state object flows between nodes and stores:
- Raw issue text
- Individual category scores
- Final computed severity score
- Final severity label

TypedDict ensures type safety across nodes.
"""

# Shared state schema passed between nodes
# total=False allows optional incremental updates

from typing import TypedDict, Optional


class SeverityState(TypedDict, total=False):
    issue: str

    clinical_score: Optional[int]
    reversibility_score: Optional[int]
    medical_score: Optional[int]
    duration_score: Optional[int]

    severity_score: Optional[int]
    severity_label: Optional[str]
