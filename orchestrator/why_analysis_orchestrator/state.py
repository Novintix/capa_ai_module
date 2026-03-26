"""
Orchestrator State Definition
Structured state for Why Analysis Orchestrator using TypedDict.
This state tracks the full lifecycle of the orchestrated Why Analysis:
  - Input context (complaint, evidence, SOP, FMEA path)
  - Iteration tracking (depth, chain history, current step results)
  - Final output (root cause, confidence, mode)
"""
from typing import TypedDict, Optional, List, Dict, Any
class WhyChainEntry(TypedDict, total=False):
    """
    A single iteration in the Why analysis chain.
    Captures the question asked, causes found, and selected root cause per depth.
    """
    depth: int
    question: str
    reasoning: str                          # Why the question was chosen
    causes_found: int                       # How many causes were returned
    causes: List[Dict[str, Any]]            # Full cause list from Cause Gen
    selected_cause: Optional[Dict[str, Any]]  # Root cause picked by Zero Evidence
    fmea_causes_exhausted: bool             # Whether FMEA had no more matches
class OrchestratorState(TypedDict, total=False):
    """
    Full orchestrator state.
    Sections:
      1. Input fields          — provided by the caller, immutable during execution
      2. Mode determination    — computed once during initialization
      3. Iteration tracking    — updated every iteration
      4. Current step results  — transient, overwritten each iteration
      5. Final output          — set when analysis completes
      6. Control fields        — graph routing & error handling
    """
    # =========================================================================
    # 1. Input fields (immutable after initialization)
    # =========================================================================
    complaint_id: str
    complaint: str
    evidence: str
    sop: str
    fmea_document_path: Optional[str]       # None → no-FMEA mode
    # =========================================================================
    # 2. Mode determination
    # =========================================================================
    has_fmea: bool                           # True if FMEA path is valid & file exists
    mode: str                                # "FMEA_ITERATIVE" | "NO_FMEA_SINGLE_SHOT"
    # =========================================================================
    # 3. Iteration tracking
    # =========================================================================
    current_depth: int                       # Current Why depth (starts at 1)
    max_depth: int                           # Maximum depth (default 5)
    why_chain: List[WhyChainEntry]           # Accumulated chain history
    # =========================================================================
    # 4. Current step results (transient — overwritten each iteration)
    # =========================================================================
    current_why_question: Optional[str]      # Latest Why question
    current_why_reasoning: Optional[str]     # Reasoning for the question
    current_causes: List[Dict[str, Any]]     # Causes from latest Cause Gen call
    current_total_causes: int                # Count of causes from Cause Gen
    current_fmea_matched: int                # Number of FMEA entries matched
    current_root_cause: Optional[Dict[str, Any]]  # Selected by Zero Evidence
    # =========================================================================
    # 5. Final output
    # =========================================================================
    final_root_cause: Optional[Dict[str, Any]]  # The definitive root cause
    final_confidence: Optional[str]             # "LOW" / "MEDIUM" / "HIGH"
    analysis_depth: int                          # Total Why depth reached
    # =========================================================================
    # 6. Control fields
    # =========================================================================
    status: str                              # "running" | "completed" | "error"
    error: Optional[str]
    next_step: Optional[str]                 # Graph routing