"""
Similar Cases Agent
Finds semantically similar complaint cases using MongoDB Atlas Vector Search.
"""

from Agents.similar_cases.agent import SimilarCasesAgent
from Agents.similar_cases.router import router
from Agents.similar_cases.state import SimilarCasesInput, SimilarCasesOutput

__all__ = [
    "SimilarCasesAgent",
    "router",
    "SimilarCasesInput",
    "SimilarCasesOutput"
]
