"""
Ranking Agent - Main entry point
Ranks candidate root causes using RCPS methodology
"""

from Agents.ranking.state import RankingInput, RankingOutput, CauseInput
from Agents.ranking.graph import ranking_graph
from Agents.ranking.logger import clear_logs, log_api_request, log_api_response, log_error


class RankingAgent:
    """
    Ranking Agent for root cause prioritization.
    
    Uses FMEA-based Risk Priority Number (RPN) combined with:
    - Evidence strength
    - Mechanism fit
    - Causal proximity
    
    To calculate Root Cause Priority Score (RCPS) and rank causes.
    """
    
    def __init__(self):
        """Initialize the ranking agent with compiled graph."""
        self.graph = ranking_graph
    
    def rank_causes(self, causes: list, config: dict = None) -> RankingOutput:
        """
        Rank candidate root causes by RCPS score with configurable parameters.
        
        Args:
            causes: List of cause dictionaries with required fields
            config: Optional configuration dictionary for domain-specific behavior
            
        Returns:
            RankingOutput with ranked causes and selected root cause
        """
        try:
            # Clear logs for new run
            clear_logs()
            
            # Create configuration
            from Agents.ranking.state import RankingConfig
            ranking_config = RankingConfig(**(config or {}))
            
            # Create input with configuration
            ranking_input = RankingInput(
                causes=[CauseInput(**c) for c in causes],
                config=ranking_config
            )
            
            log_api_request(f"/ranking ({ranking_config.domain})", len(causes))
            
            # Run graph
            result = self.graph.invoke({"input": ranking_input})
            
            # Extract output
            output = result["final_output"]
            
            log_api_response(output.total_causes, output.selected_root_cause)
            
            return output
            
        except Exception as e:
            error_msg = f"Ranking agent failed: {str(e)}"
            log_error("rank_causes", error_msg)
            raise Exception(error_msg)
