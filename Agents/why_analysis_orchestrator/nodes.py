"""
Orchestrator Nodes
All node functions for the Why Analysis Orchestrator.
Node responsibilities:
  1. initialize_node         — Determine mode, set up state
  2. generate_question_node  — Call Question Agent to produce the next Why
  3. generate_causes_node    — Call Cause Generation Agent to find/generate causes
  4. rank_causes_node        — Call Zero Evidence Agent to select top cause
  5. check_iteration_node    — Decide: iterate (FMEA mode) or stop
  6. finalize_node           — Package the final root cause output
Design rules:
  - Each node has a SINGLE responsibility
  - Nodes call sub-agents via their Python classes (not HTTP)
  - Orchestration logic lives in graph.py, not here
  - All nodes return a partial state dict to be merged
"""
import os
from typing import Dict, Any, List
from .state import OrchestratorState, WhyChainEntry
from .logger import (
    log_node_entry, log_node_exit, log_routing_decision,
    log_error, log_iteration
)
# Sub-agent imports — direct class usage, no HTTP
from Agents.question.schemas import StartWhyInput, ContinueWhyInput
from Agents.question.agent import WhyQuestionAgent
from Agents.cause_generation.schemas import QuestionInput
from Agents.cause_generation.agent import CauseGenerationAgent
from Agents.zero_evidence_agent.schemas import ZeroEvidenceInput, CauseInput
from Agents.zero_evidence_agent.agent import ZeroEvidenceAgent
from langgraph.graph import END
# =============================================================================
# LAZY SINGLETON SUB-AGENTS
# =============================================================================
_question_agent: WhyQuestionAgent = None
_cause_agent: CauseGenerationAgent = None
_zero_evidence_agent: ZeroEvidenceAgent = None
def _get_question_agent() -> WhyQuestionAgent:
    global _question_agent
    if _question_agent is None:
        _question_agent = WhyQuestionAgent()
    return _question_agent
def _get_cause_agent() -> CauseGenerationAgent:
    global _cause_agent
    if _cause_agent is None:
        _cause_agent = CauseGenerationAgent()
    return _cause_agent
def _get_zero_evidence_agent() -> ZeroEvidenceAgent:
    global _zero_evidence_agent
    if _zero_evidence_agent is None:
        _zero_evidence_agent = ZeroEvidenceAgent()
    return _zero_evidence_agent
# =============================================================================
# NODE 1 — Initialize
# =============================================================================
def initialize_node(state: OrchestratorState) -> dict:
    """
    Node: Initialize orchestrator state.
    Responsibilities:
      - Determine analysis mode (FMEA iterative vs no-FMEA single-shot)
      - Validate FMEA file exists (if path provided)
      - Set up iteration defaults
    """
    log_node_entry("initialize", state)
    fmea_path = state.get("fmea_document_path")
    has_fmea = False
    if fmea_path and os.path.exists(fmea_path):
        has_fmea = True
    mode = "FMEA_ITERATIVE" if has_fmea else "NO_FMEA_SINGLE_SHOT"
    updates = {
        "has_fmea": has_fmea,
        "mode": mode,
        "current_depth": 0,
        "max_depth": 5,
        "why_chain": [],
        "current_why_question": None,
        "current_why_reasoning": None,
        "current_causes": [],
        "current_total_causes": 0,
        "current_fmea_matched": 0,
        "current_root_cause": None,
        "final_root_cause": None,
        "final_confidence": None,
        "analysis_depth": 0,
        "status": "running",
        "error": None,
        "next_step": "generate_question",
    }
    log_routing_decision("initialize", "generate_question", f"Mode: {mode}, has_fmea: {has_fmea}")
    log_node_exit("initialize", updates)
    return updates
# =============================================================================
# NODE 2 — Generate Question
# =============================================================================
def generate_question_node(state: OrchestratorState) -> dict:
    """
    Node: Generate the next Why question using the Question Agent.
    On first call (depth=0): uses StartWhyInput (full context).
    On subsequent calls: uses ContinueWhyInput (complaint_id + previous answer).
    The "answer" for continuation is the selected cause from the previous iteration.
    """
    log_node_entry("generate_question", state)
    try:
        agent = _get_question_agent()
        current_depth = state.get("current_depth", 0)
        why_chain = state.get("why_chain", [])
        if current_depth == 0:
            # First Why — provide full context
            start_input = StartWhyInput(
                complaint_id=state["complaint_id"],
                complaint=state["complaint"],
                evidence=state["evidence"],
                sop=state["sop"],
            )
            result = agent.start(start_input)
        else:
            # Subsequent Why — provide previous root cause as the "answer"
            previous_root_cause = state.get("current_root_cause", {})
            answer = previous_root_cause.get("cause_text", "Unknown cause")
            continue_input = ContinueWhyInput(
                complaint_id=state["complaint_id"],
                answer=answer,
            )
            result = agent.continue_chain(continue_input)
        # Check result
        if result.get("error") or not result.get("why_question"):
            error_msg = result.get("error", "Question generation failed with no details.")
            log_error("generate_question", error_msg)
            updates = {
                "error": error_msg,
                "status": "error",
                "next_step": "finalize",
            }
            log_routing_decision("generate_question", "finalize", f"Error: {error_msg}")
            log_node_exit("generate_question", updates)
            return updates
        new_depth = current_depth + 1
        updates = {
            "current_depth": new_depth,
            "current_why_question": result["why_question"],
            "current_why_reasoning": result.get("reasoning", ""),
            "error": None,
            "next_step": "generate_causes",
        }
        log_routing_decision(
            "generate_question", "generate_causes",
            f"Depth {new_depth}: {result['why_question'][:80]}..."
        )
        log_node_exit("generate_question", updates)
        return updates
    except Exception as e:
        error_msg = f"Question generation failed: {str(e)}"
        log_error("generate_question", error_msg)
        updates = {
            "error": error_msg,
            "status": "error",
            "next_step": "finalize",
        }
        log_routing_decision("generate_question", "finalize", "Exception")
        log_node_exit("generate_question", updates)
        return updates
# =============================================================================
# NODE 3 — Generate Causes
# =============================================================================
def generate_causes_node(state: OrchestratorState) -> dict:
    """
    Node: Generate causes using the Cause Generation Agent.
    Input to Cause Gen:
      - question    : The current Why question
      - context     : The complaint text (for domain context)
      - fmea_path   : Passed through from orchestrator input (may be None)
    Cause Gen internally decides:
      - If FMEA path provided & valid → parse FMEA, match, extract causes
      - If no FMEA → generate via LLM
    """
    log_node_entry("generate_causes", state)
    try:
        agent = _get_cause_agent()
        question_input = QuestionInput(
            question_id=f"{state['complaint_id']}_depth{state['current_depth']}",
            question=state["current_why_question"],
            context=state.get("complaint", ""),
        )
        fmea_path = state.get("fmea_document_path") if state.get("has_fmea") else None
        result = agent.process_question(question_input, fmea_path)
        causes = result.get("causes", [])
        total_causes = result.get("total_causes", 0)
        matched_entries = result.get("matched_entries", 0)
        updates = {
            "current_causes": causes,
            "current_total_causes": total_causes,
            "current_fmea_matched": matched_entries,
            "error": None,
        }
        if total_causes == 0:
            # No causes found — this is a natural stop condition
            # Record this iteration with 0 causes and go to finalize
            chain_entry: WhyChainEntry = {
                "depth": state["current_depth"],
                "question": state["current_why_question"],
                "reasoning": state.get("current_why_reasoning", ""),
                "causes_found": 0,
                "causes": [],
                "selected_cause": None,
                "fmea_causes_exhausted": True,
            }
            updated_chain = list(state.get("why_chain", []))
            updated_chain.append(chain_entry)
            updates["why_chain"] = updated_chain
            updates["next_step"] = "finalize"
            log_routing_decision("generate_causes", "finalize", "No causes found — stopping")
        else:
            updates["next_step"] = "rank_causes"
            log_routing_decision("generate_causes", "rank_causes", f"{total_causes} causes to rank")
        log_node_exit("generate_causes", updates)
        return updates
    except Exception as e:
        error_msg = f"Cause generation failed: {str(e)}"
        log_error("generate_causes", error_msg)
        updates = {
            "current_causes": [],
            "current_total_causes": 0,
            "error": error_msg,
            "next_step": "finalize",
        }
        log_routing_decision("generate_causes", "finalize", "Exception")
        log_node_exit("generate_causes", updates)
        return updates
# =============================================================================
# NODE 4 — Rank Causes
# =============================================================================
def rank_causes_node(state: OrchestratorState) -> dict:
    """
    Node: Rank causes using the Zero Evidence Agent.
    Input: current_causes list from Cause Gen
    Output: selected root cause (the highest-ranked cause)
    """
    log_node_entry("rank_causes", state)
    try:
        agent = _get_zero_evidence_agent()
        causes = state.get("current_causes", [])
        if not causes:
            log_error("rank_causes", "No causes to rank")
            updates = {
                "current_root_cause": None,
                "next_step": "finalize",
            }
            log_routing_decision("rank_causes", "finalize", "Empty causes list")
            log_node_exit("rank_causes", updates)
            return updates
        # Build CauseInput list for Zero Evidence Agent
        cause_inputs = []
        for cause in causes:
            cause_inputs.append(CauseInput(
                cause_id=cause.get("cause_id", "UNKNOWN"),
                cause_text=cause.get("cause_text", ""),
                process_step=cause.get("process_step", ""),
                failure_mode=cause.get("failure_mode", ""),
                potential_effects=cause.get("potential_effects"),
                severity=cause.get("severity"),
                occurrence=cause.get("occurrence"),
                detection=cause.get("detection"),
                current_controls=cause.get("current_controls"),
                source=cause.get("source", "FMEA"),
            ))
        zero_input = ZeroEvidenceInput(
            question_id=f"{state['complaint_id']}_depth{state['current_depth']}",
            question=state["current_why_question"],
            causes=cause_inputs,
            total_causes=len(cause_inputs),
        )
        result = agent.analyze(zero_input)
        selected_root_cause = result.get("selected_root_cause")
        if not selected_root_cause:
            log_error("rank_causes", f"Zero Evidence returned no cause: {result.get('error')}")
            # Still proceed — use the first cause as fallback
            if causes:
                selected_root_cause = {
                    "cause_id": causes[0].get("cause_id", "C001"),
                    "cause_text": causes[0].get("cause_text", ""),
                    "process_step": causes[0].get("process_step", ""),
                    "reason": "Fallback — Zero Evidence Agent failed; using first cause.",
                }
        updates = {
            "current_root_cause": selected_root_cause,
            "error": None,
            "next_step": "check_iteration",
        }
        log_routing_decision("rank_causes", "check_iteration", f"Selected: {selected_root_cause.get('cause_id', 'N/A') if selected_root_cause else 'None'}")
        log_node_exit("rank_causes", updates)
        return updates
    except Exception as e:
        error_msg = f"Cause ranking failed: {str(e)}"
        log_error("rank_causes", error_msg)
        updates = {
            "current_root_cause": None,
            "error": error_msg,
            "next_step": "finalize",
        }
        log_routing_decision("rank_causes", "finalize", "Exception")
        log_node_exit("rank_causes", updates)
        return updates
# =============================================================================
# NODE 5 — Check Iteration
# =============================================================================
def check_iteration_node(state: OrchestratorState) -> dict:
    """
    Node: Decide whether to iterate or stop.
    Records the current iteration in why_chain, then applies stop rules:
    Stop conditions:
      1. NO_FMEA_SINGLE_SHOT mode → always stop after first iteration
      2. FMEA_ITERATIVE mode → stop when:
         a. Max depth reached
         b. FMEA matched entries = 0 in this iteration
         c. No root cause was selected (error)
    Continue condition:
      - FMEA_ITERATIVE mode with more depth available and causes were found
    """
    log_node_entry("check_iteration", state)
    mode = state.get("mode", "NO_FMEA_SINGLE_SHOT")
    current_depth = state.get("current_depth", 1)
    max_depth = state.get("max_depth", 5)
    fmea_matched = state.get("current_fmea_matched", 0)
    root_cause = state.get("current_root_cause")
    causes = state.get("current_causes", [])
    # Record this iteration in the chain
    chain_entry: WhyChainEntry = {
        "depth": current_depth,
        "question": state.get("current_why_question", ""),
        "reasoning": state.get("current_why_reasoning", ""),
        "causes_found": len(causes),
        "causes": causes,
        "selected_cause": root_cause,
        "fmea_causes_exhausted": (fmea_matched == 0),
    }
    updated_chain = list(state.get("why_chain", []))
    updated_chain.append(chain_entry)
    # Log the iteration
    log_iteration(
        current_depth,
        state.get("current_why_question", ""),
        len(causes),
        root_cause.get("cause_text", "N/A") if root_cause else None,
    )
    updates = {
        "why_chain": updated_chain,
        "analysis_depth": current_depth,
    }
    # --- Stop decision ---
    # Rule 1: No-FMEA mode → always stop after first iteration
    if mode == "NO_FMEA_SINGLE_SHOT":
        updates["final_root_cause"] = root_cause
        updates["final_confidence"] = "MEDIUM"
        updates["status"] = "completed"
        updates["next_step"] = "finalize"
        log_routing_decision("check_iteration", "finalize", "NO_FMEA mode — single shot complete")
        log_node_exit("check_iteration", updates)
        return updates
    # Rule 2: Max depth reached
    if current_depth >= max_depth:
        updates["final_root_cause"] = root_cause
        updates["final_confidence"] = "MEDIUM"
        updates["status"] = "completed"
        updates["next_step"] = "finalize"
        log_routing_decision("check_iteration", "finalize", f"Max depth ({max_depth}) reached")
        log_node_exit("check_iteration", updates)
        return updates
    # Rule 3: No root cause selected (error scenario)
    if not root_cause:
        # Use the last successfully selected cause as final
        last_good_cause = None
        for entry in reversed(updated_chain):
            if entry.get("selected_cause"):
                last_good_cause = entry["selected_cause"]
                break
        updates["final_root_cause"] = last_good_cause
        updates["final_confidence"] = "LOW"
        updates["status"] = "completed"
        updates["next_step"] = "finalize"
        log_routing_decision("check_iteration", "finalize", "No root cause — using last good cause")
        log_node_exit("check_iteration", updates)
        return updates
    # --- Continue: FMEA mode with more depth available ---
    updates["next_step"] = "generate_question"
    log_routing_decision(
        "check_iteration", "generate_question",
        f"FMEA_ITERATIVE — continuing to depth {current_depth + 1}"
    )
    log_node_exit("check_iteration", updates)
    return updates
# =============================================================================
# NODE 6 — Finalize
# =============================================================================
def finalize_node(state: OrchestratorState) -> dict:
    """
    Node: Package the final output.
    If final_root_cause is already set (by check_iteration), preserves it.
    If not set (direct jump from error), attempts to extract from why_chain.
    Always sets:
      - status = "completed" (or "error" if no root cause at all)
      - next_step = END
    """
    log_node_entry("finalize", state)
    final_root_cause = state.get("final_root_cause")
    final_confidence = state.get("final_confidence", "MEDIUM")
    # If no root cause was set yet, try to recover from chain
    if not final_root_cause:
        why_chain = state.get("why_chain", [])
        for entry in reversed(why_chain):
            if entry.get("selected_cause"):
                final_root_cause = entry["selected_cause"]
                final_confidence = "LOW"
                break
    status = "completed" if final_root_cause else "error"
    error = state.get("error") if not final_root_cause else None
    if not final_root_cause and not error:
        error = "Analysis completed but no root cause could be determined."
    updates = {
        "final_root_cause": final_root_cause,
        "final_confidence": final_confidence,
        "analysis_depth": state.get("current_depth", 0),
        "status": status,
        "error": error,
        "next_step": END,
    }
    log_routing_decision("finalize", "END", f"Status: {status}")
    log_node_exit("finalize", updates)
    return updates