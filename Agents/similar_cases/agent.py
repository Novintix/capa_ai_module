"""
Similar Cases Agent
Main agent class that uses the LangGraph workflow.
"""

from typing import Dict, Any
from Agents.similar_cases.graph import create_similar_cases_graph
from Agents.similar_cases.state import SimilarCasesState, SimilarCasesInput, SimilarCasesOutput
from Agents.similar_cases.logger import log_request, log_final_output
from agent_ops import agentops_agent, agentops_operation


@agentops_agent(name="similar_cases_agent")
class SimilarCasesAgent:
    """
    Similar Cases Agent using LangGraph.
    Finds semantically similar complaints using MongoDB Atlas Vector Search.
    """
    
    def __init__(self):
        """Initialize the agent with compiled graph."""
        self.graph = create_similar_cases_graph()
    
    @agentops_operation(name="find_similar_cases")
    def find_similar_cases(self, query: str) -> SimilarCasesOutput:
        """
        Find similar cases for a given complaint description.
        
        Args:
            query: Complaint description text
            
        Returns:
            SimilarCasesOutput with matching cases and metadata
        """
        # Log request
        log_request(query)
        
        # Initialize state
        initial_state = SimilarCasesState(
            input=SimilarCasesInput(query=query),
            iteration=0
        )
        
        # Run graph - returns dict
        final_state_dict = self.graph.invoke(initial_state)
        
        # Convert dict to state object if needed
        if isinstance(final_state_dict, dict):
            final_state = SimilarCasesState(**final_state_dict)
        else:
            final_state = final_state_dict
        
        # Log final output
        if final_state.final_output:
            log_final_output(
                final_state.final_output.similarCount,
                final_state.final_output.similarityThreshold
            )
        
        # Return result
        if final_state.error:
            raise Exception(final_state.error)
        
        return final_state.final_output
