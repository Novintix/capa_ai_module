from .graph import create_pattern_graph
from .schemas import PatternAnalysisRequest, PatternAnalysisResponse
from .state import AgentState
from agent_ops import agentops_agent, agentops_operation

@agentops_agent(name="pattern_agent")
class PatternAgentLangGraph:
    """
    Pattern Agent for Trend Analysis and Pattern Recognition.
    """
    
    def __init__(self):
        self.graph = create_pattern_graph()
    
    @agentops_operation(name="process_pattern")
    def process_pattern(self, request: PatternAnalysisRequest) -> dict:
        """Run the Pattern Agent with the given request."""
        
        # Initialize state from request
        initial_state: AgentState = {
            "complaint_id": request.complaint_id,
            "complaint_description": request.description,
            "historical_complaints": [],
            "trend_score": None,
            "trend_category": None,
            "confidence": None,
            "explanation": None,
            "iteration": 0,
            "max_iterations": 3,
            "error": None,
            "next_step": "initialize"
        }
        
        # Execute graph
        final_state = self.graph.invoke(initial_state)
        
        # Map state to response dict
        return {
            "complaint_id": final_state["complaint_id"],
            "trend_score": final_state.get("trend_score", 1),
            "trend_category": final_state.get("trend_category", "Error or No Trend"),
            "confidence": final_state.get("confidence", 0.0),
            "explanation": final_state.get("explanation", "Analysis failed to produce a result."),
            "matched_complaint_ids": final_state.get("matched_complaint_ids", []),
            "identified_pattern": final_state.get("identified_pattern"),
            "error": final_state.get("error")
        }
