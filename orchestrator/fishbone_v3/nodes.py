"""
Fishbone V3 Orchestrator Nodes
Individual node functions for the LangGraph workflow
"""
from typing import Dict, Any
from .state import FishboneV3State
from .logger import log_agent_call, log_error, log_state_transition
from Agents.cause_generation.agent import CauseGenerationAgent
from Agents.cause_generation.schemas import QuestionInput
from Agents.categorize.graph import categorize_graph
from Agents.categorize.state import CategorizeState, CategorizeInput, Cause
from Agents.validation.agent import ValidationAgent
from Agents.validation.schemas import ValidationInput, GeneratedCause


# Initialize agents
cause_agent = CauseGenerationAgent()
validation_agent = ValidationAgent()


def initialize_node(state: FishboneV3State) -> Dict[str, Any]:
    """Initialize the workflow"""
    log_state_transition("START", "initialize", "Starting Fishbone V3 analysis")
    
    return {
        "execution_trace": ["1. Initialize"],
        "next_step": "list_causes",
        "status": "INITIALIZING"
    }


def list_causes_node(state: FishboneV3State) -> Dict[str, Any]:
    """Generate causes from complaint using Cause Generation Agent"""
    log_state_transition("initialize", "list_causes", "Listing causes")
    log_agent_call("ListCausesAgent", {"id": state["complaint_id"]}, None)
    
    try:
        question_input = QuestionInput(
            question_id=f"{state['complaint_id']}_v3",
            question=f"What are the potential causes of: {state['complaint']}",
            context=state["complaint"]
        )
        
        result = cause_agent.process_question(
            question_input, 
            state.get("fmea_document_path")
        )
        causes = result.get("causes", [])
        
        log_agent_call("ListCausesAgent", {"found": len(causes)}, True)
        
        if not causes:
            return {
                "causes": [],
                "execution_trace": state["execution_trace"] + ["2. ListCausesAgent - No causes found"],
                "next_step": "complete_analysis",
                "status": "ERROR",
                "error": "No causes found"
            }
        
        return {
            "causes": causes,
            "execution_trace": state["execution_trace"] + [f"2. ListCausesAgent - Found {len(causes)} causes"],
            "next_step": "categorize_causes",
            "status": "LISTING_CAUSES"
        }
    
    except Exception as e:
        log_error("list_causes_node", str(e))
        return {
            "causes": [],
            "execution_trace": state["execution_trace"] + [f"2. ListCausesAgent - Error: {str(e)}"],
            "next_step": "complete_analysis",
            "status": "ERROR",
            "error": str(e)
        }


def categorize_causes_node(state: FishboneV3State) -> Dict[str, Any]:
    """Categorize causes into 6M categories"""
    log_state_transition("list_causes", "categorize_causes", "Categorizing causes")
    
    try:
        causes = state["causes"]
        categorize_causes = [
            Cause(
                cause_id=c.get("cause_id"),
                cause_text=c.get("cause_text"),
                process_step=c.get("process_step"),
                failure_mode=c.get("failure_mode"),
                potential_effects=c.get("potential_effects"),
                severity=c.get("severity"),
                occurrence=c.get("occurrence"),
                detection=c.get("detection"),
                current_controls=c.get("current_controls"),
                source=c.get("source")
            ) for c in causes
        ]
        
        categorize_input = CategorizeInput(
            question=state["complaint"],
            causes=categorize_causes
        )
        
        result = categorize_graph.invoke(CategorizeState(input=categorize_input, iteration=0))
        output = result.get("final_output")
        
        if output:
            cat_map = {c.cause_id: c for c in output.categorized_causes}
            for cause in causes:
                match = cat_map.get(cause["cause_id"])
                if match:
                    cause.update({
                        "category": match.category,
                        "category_confidence": match.confidence,
                        "category_reasoning": match.reasoning
                    })
            
            return {
                "categorized_causes": causes,
                "category_summary": output.summary,
                "execution_trace": state["execution_trace"] + ["3. CategorizationAgent - Completed"],
                "next_step": "validate_causes",
                "status": "CATEGORIZING"
            }
        
        return {
            "categorized_causes": causes,
            "category_summary": {},
            "execution_trace": state["execution_trace"] + ["3. CategorizationAgent - No output"],
            "next_step": "validate_causes",
            "status": "CATEGORIZING"
        }
    
    except Exception as e:
        log_error("categorize_causes_node", str(e))
        return {
            "categorized_causes": state["causes"],
            "category_summary": {},
            "execution_trace": state["execution_trace"] + [f"3. CategorizationAgent - Error: {str(e)}"],
            "next_step": "complete_analysis",
            "status": "ERROR",
            "error": str(e)
        }


def validate_causes_node(state: FishboneV3State) -> Dict[str, Any]:
    """Validate causes against evidence"""
    log_state_transition("categorize_causes", "validate_causes", "Validating causes")
    
    try:
        causes = state["categorized_causes"]
        generated = [
            GeneratedCause(cause_id=c["cause_id"], cause_text=c["cause_text"]) 
            for c in causes
        ]
        
        v_input = ValidationInput(
            complaint_id=state["complaint_id"],
            question=state["complaint"],
            generated_causes=generated,
            complaint_description=state["complaint"],
            investigation_evidence=state.get("evidence", "")
        )
        
        result = validation_agent.validate_causes(v_input)
        val_map = {vc["cause_id"]: vc for vc in result.get("validated_causes", [])}
        
        validated_causes = []
        for cause in causes:
            match = val_map.get(cause["cause_id"])
            if match:
                cause.update({
                    "validation_status": match.get("evidence_match_status"),
                    "validation_confidence": match.get("confidence"),
                    "validation_rationale": match.get("rationale")
                })
                validated_causes.append(cause)
        
        return {
            "categorized_causes": causes,
            "validated_causes": validated_causes,
            "validation_confidence": result.get("overall_confidence", 0.0),
            "execution_trace": state["execution_trace"] + ["4. ValidationAgent - Completed"],
            "next_step": "filter_high_confidence",
            "status": "VALIDATING"
        }
    
    except Exception as e:
        log_error("validate_causes_node", str(e))
        return {
            "validated_causes": [],
            "validation_confidence": 0.0,
            "execution_trace": state["execution_trace"] + [f"4. ValidationAgent - Error: {str(e)}"],
            "next_step": "complete_analysis",
            "status": "ERROR",
            "error": str(e)
        }


def filter_high_confidence_node(state: FishboneV3State) -> Dict[str, Any]:
    """Filter causes with validation_confidence >= 0.9"""
    log_state_transition("validate_causes", "filter_high_confidence", "Filtering high confidence causes")
    
    try:
        all_causes = state["categorized_causes"]
        high_confidence_causes = [
            c for c in all_causes 
            if c.get("validation_confidence", 0.0) >= 0.9
        ]
        
        if high_confidence_causes:
            return {
                "high_confidence_causes": high_confidence_causes,
                "execution_trace": state["execution_trace"] + [f"5. Filter - Found {len(high_confidence_causes)} high confidence causes"],
                "next_step": "wait_for_human",
                "status": "WAIT_FOR_HUMAN"
            }
        else:
            return {
                "high_confidence_causes": [],
                "execution_trace": state["execution_trace"] + ["5. Filter - No high confidence causes"],
                "next_step": "complete_analysis",
                "status": "COMPLETED"
            }
    
    except Exception as e:
        log_error("filter_high_confidence_node", str(e))
        return {
            "high_confidence_causes": [],
            "execution_trace": state["execution_trace"] + [f"5. Filter - Error: {str(e)}"],
            "next_step": "complete_analysis",
            "status": "ERROR",
            "error": str(e)
        }


def wait_for_human_node(state: FishboneV3State) -> Dict[str, Any]:
    """Pause and wait for human decisions"""
    log_state_transition("filter_high_confidence", "wait_for_human", "Waiting for human review")
    
    # This node just marks the state as waiting
    # The actual human input comes through the submit_decisions API
    return {
        "execution_trace": state["execution_trace"] + ["6. WaitForHuman - Paused"],
        "next_step": "record_decisions",
        "status": "WAIT_FOR_HUMAN"
    }


def record_decisions_node(state: FishboneV3State) -> Dict[str, Any]:
    """Record human decisions (RCA/PROCEED)"""
    log_state_transition("wait_for_human", "record_decisions", "Recording human decisions")
    
    try:
        decisions = state.get("human_decisions", [])
        decisions_dict = {d["cause_id"]: d for d in decisions}
        
        # Apply decisions to high confidence causes
        for cause in state["high_confidence_causes"]:
            cid = cause.get("cause_id")
            if cid in decisions_dict:
                decision = decisions_dict[cid]
                cause["human_decision"] = decision.get("action")
                cause["human_comment"] = decision.get("comment")
        
        return {
            "high_confidence_causes": state["high_confidence_causes"],
            "execution_trace": state["execution_trace"] + [f"7. RecordDecisions - Recorded {len(decisions)} decisions"],
            "next_step": "complete_analysis",
            "status": "RECORDING_DECISIONS"
        }
    
    except Exception as e:
        log_error("record_decisions_node", str(e))
        return {
            "execution_trace": state["execution_trace"] + [f"7. RecordDecisions - Error: {str(e)}"],
            "next_step": "complete_analysis",
            "status": "ERROR",
            "error": str(e)
        }


def complete_analysis_node(state: FishboneV3State) -> Dict[str, Any]:
    """Complete the analysis"""
    log_state_transition("record_decisions", "complete_analysis", "Completing analysis")
    
    return {
        "execution_trace": state["execution_trace"] + ["8. Complete"],
        "next_step": "end",
        "status": "COMPLETED"
    }
