import json
import os
import httpx
import asyncio
from dotenv import load_dotenv
from typing import Any, Dict, Optional
from orchestrator_service.state import RiskAssessmentState
from orchestrator_service.logger import log_node_entry, log_node_exit, log_error
from langchain_core.runnables import RunnableConfig

load_dotenv()

# ── Severity Agent ────────────────────────────────────────────────────────────
# Runs as a separate FastAPI service. Expects: {"issue": str}
# Returns: severity_score, severity_label, clinical_score, etc.
SEVERITY_SERVICE_URL = os.getenv("SEVERITY_SERVICE_URL", "http://localhost:8000/severity")

def call_severity_agent(issue: str) -> Dict[str, Any]:
    """HTTP POST to the Severity microservice."""
    try:
        response = httpx.post(SEVERITY_SERVICE_URL, json={"issue": issue}, timeout=10.0)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        log_error("call_severity_agent", e)
        raise

# ── Occurrence Agent ──────────────────────────────────────────────────────────
# Runs as a separate FastAPI service. Expects Form-Data.
OCCURRENCE_SERVICE_URL = os.getenv("OCCURRENCE_SERVICE_URL", "http://localhost:8000/occurrence/analyze")

def call_occurrence_agent(payload: Dict[str, Any]) -> Dict[str, Any]:
    """HTTP POST to the Occurrence microservice using Form-Data."""
    try:
        # Prepare Form-Data
        files = {
            "complaint_id": (None, str(payload.get("complaint_id", ""))),
            "description": (None, str(payload.get("description", ""))),
            "date": (None, str(payload.get("date", ""))),
            "additional_context": (None, str(payload.get("additional_context", ""))),
            "product": (None, str(payload.get("product", ""))),
            "similar_cases_json": (None, json.dumps(payload.get("similar_cases", []))),
            "source": (None, str(payload.get("source", ""))),
        }
        
        response = httpx.post(OCCURRENCE_SERVICE_URL, data=files, timeout=10.0)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        log_error("call_occurrence_agent", e)
        raise

# ── Detection Agent ───────────────────────────────────────────────────────────
# Runs as a separate FastAPI service. Expects: {"complaint_id": str, "source": str, "description": str}
DETECTION_SERVICE_URL = os.getenv("DETECTION_SERVICE_URL", "http://localhost:8000/detection/")
DETECTION_POLICY_PATH = os.getenv("DETECTION_POLICY_PATH")

def call_detection_agent(payload: Dict[str, Any], policy_path: Optional[str] = None) -> Dict[str, Any]:
    """HTTP POST to the Detection microservice."""
    try:
        params = {}
        if policy_path:
            params["policy_path"] = policy_path
        
        # Build JSON body
        body = {
            "complaint_id": payload.get("complaint_id"),
            "source": payload.get("source"),
            "description": payload.get("description")
        }
        
        response = httpx.post(DETECTION_SERVICE_URL, json=body, params=params, timeout=10.0)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        log_error("call_detection_agent", e)
        raise

# ── Policy Constants ──────────────────────────────────────────────────────────
POLICY_CRITICAL_SEVERITY = 9
POLICY_RPN_THRESHOLD = 300
POLICY_CONFIDENCE_THRESHOLD = 0.7
SCORE_MIN = 1
SCORE_MAX = 10


def _validate_agent_output(output: Dict[str, Any]) -> str:
    """Returns None if valid, else an error message string."""
    if not isinstance(output, dict):
        return "Output is not a dictionary"
    score = output.get("score")
    if score is None:
        return "Missing numeric score"
    if not isinstance(score, (int, float)) or not (SCORE_MIN <= score <= SCORE_MAX):
        return f"Score {score} out of policy range ({SCORE_MIN}-{SCORE_MAX})"
    confidence = output.get("confidence")
    if confidence is None:
        return "Missing confidence score"
    if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
        return "Invalid confidence value"
    if not output.get("reasoning"):
        return "Missing explanation/reasoning"
    return None


import json
import httpx
from config.aws_bedrock_config import get_llm
from langgraph.types import Command
from langgraph.constants import Send

# ─────────────────────────────────────────────────────────────────────────────
# NODE: Input Validator
# ─────────────────────────────────────────────────────────────────────────────
def input_validator_node(state: RiskAssessmentState, config: RunnableConfig) -> Dict[str, Any]:
    thread_id = config["configurable"].get("thread_id")
    log_node_entry("input_validator_node", state, thread_id=thread_id)

    errors = []
    if not state.get("complaint_description"):
        errors.append("Missing complaint_description")
    if not state.get("complaint_id"):
        errors.append("Missing complaint_id")
    
    update = {}
    if errors:
        update["workflow_status"] = "halted"
        update["errors"] = errors
    else:
        update["orchestrator_log"] = ["Input validated successfully."]
        
    log_node_exit("input_validator_node", update, thread_id=thread_id)
    return update

# ─────────────────────────────────────────────────────────────────────────────
# NODE: Orchestrator Brain (Bedrock)
# ─────────────────────────────────────────────────────────────────────────────
def orchestrator_brain_node(state: RiskAssessmentState, config: RunnableConfig) -> Dict[str, Any]:
    thread_id = config["configurable"].get("thread_id")
    log_node_entry("orchestrator_brain_node", state, thread_id=thread_id)

    llm = get_llm()
    prompt = f"""
    You are the Lead Orchestrator for a Risk Assessment System.
    Analyze the following complaint and decide which specialized workers are needed.
    
    COMPLAINT:
    ID: {state['complaint_id']}
    Description: {state['complaint_description']}
    Metadata: {state.get('product', 'N/A')}, {state.get('source', 'N/A')}
    
    AVAILABLE WORKERS:
    - severity_worker: Analyzes clinical severity and impact on patient safety.
    - occurrence_worker: Analyzes how often this issue happens based on history.
    - detection_worker: Analyzes how easy/hard it is to detect this issue before it causes harm.
    - historical_pattern_worker: Looks for specific historical trends or clusters (useful for complex patterns).
    - regulatory_impact_worker: Checks if this triggers specific regulatory reporting (FDA, MDR, etc.).
    
    RULES:
    - ALWAYS include occurrence_worker.
    - If the complaint mentions "death", "injury", or "critical", include regulatory_impact_worker.
    - If there are similar cases provided, include historical_pattern_worker.
    
    Return ONLY a JSON object:
    {{
        "complaint_type": "string",
        "workers_needed": ["list", "of", "worker_names"],
        "reasoning": "brief explanation of the plan"
    }}
    """
    
    try:
        response = llm.invoke(prompt)
        plan = json.loads(response.content)
        update = {
            "execution_plan": plan,
            "orchestrator_log": [f"Brain generated plan: {plan['reasoning']}"]
        }
    except Exception as e:
        log_error("orchestrator_brain_node", e, thread_id=thread_id)
        update = {"errors": [f"Orchestrator Brain Error: {str(e)}"], "workflow_status": "halted"}

    log_node_exit("orchestrator_brain_node", update, thread_id=thread_id)
    return update

# ─────────────────────────────────────────────────────────────────────────────
# WORKER NODES (Dynamic Dispatch to Real Services)
# ─────────────────────────────────────────────────────────────────────────────

def severity_worker(state: RiskAssessmentState, config: RunnableConfig) -> Dict[str, Any]:
    thread_id = config["configurable"].get("thread_id")
    payload = {"issue": state["complaint_description"]}
    
    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post("http://localhost:8000/severity", json=payload)
            response.raise_for_status()
            data = response.json()
            
            result = {
                "worker_name": "severity_worker",
                "score": data.get("severity_score"),
                "confidence": 1.0,
                "rationale": data.get("severity_label"),
                "flags": []
            }
            if data.get("severity_score", 0) >= 7:
                result["flags"].append("critical")
                
            return {"worker_results": [result]}
    except Exception as e:
        log_error("severity_worker", e, thread_id=thread_id)
        return {"errors": [f"Severity Worker Error: {str(e)}"]}

def occurrence_worker(state: RiskAssessmentState, config: RunnableConfig) -> Dict[str, Any]:
    thread_id = config["configurable"].get("thread_id")
    
    # Occurrence Agent expects Form Data (multipart/form-data or application/x-www-form-urlencoded)
    # similar_cases must be a JSON string
    similar_cases_json = json.dumps(state.get("similar_cases", []))
    
    payload = {
        "complaint_id": state["complaint_id"],
        "description": state["complaint_description"],
        "source": state.get("source", ""),
        "date": state.get("date", ""),
        "product": state.get("product", ""),
        "additional_context": state.get("additional_context", ""),
        "similar_cases_json": similar_cases_json
    }
    
    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post("http://localhost:8000/occurrence/analyze", data=payload)
            response.raise_for_status()
            data = response.json()
            
            breakdown = data.get("breakdown", {})
            result = {
                "worker_name": "occurrence_worker",
                "score": data.get("weighted_score", data.get("score")),
                "confidence": 0.85,
                "rationale": breakdown.get("reasoning", data.get("rating", "Occurrence analyzed.")),
                "flags": []
            }
            return {"worker_results": [result]}
    except Exception as e:
        log_error("occurrence_worker", e, thread_id=thread_id)
        return {"errors": [f"Occurrence Worker Error: {str(e)}"]}

def detection_worker(state: RiskAssessmentState, config: RunnableConfig) -> Dict[str, Any]:
    thread_id = config["configurable"].get("thread_id")
    
    # Detection Agent expects complaint object in root but as JSON
    # policy_path is a query parameter
    payload = {
        "complaint_id": state["complaint_id"],
        "source": state.get("source", ""),
        "description": state["complaint_description"]
    }
    
    params = {}
    if state.get("policy_path"):
        params["policy_path"] = state["policy_path"]
        
    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post("http://localhost:8000/detection/", json=payload, params=params)
            response.raise_for_status()
            data = response.json()
            
            result = {
                "worker_name": "detection_worker",
                "score": data.get("detection_score", data.get("score")),
                "confidence": data.get("confidence", 0.95),
                "rationale": data.get("explanation", data.get("reasoning", "Detection analyzed.")),
                "flags": []
            }
            return {"worker_results": [result]}
    except Exception as e:
        log_error("detection_worker", e, thread_id=thread_id)
        return {"errors": [f"Detection Worker Error: {str(e)}"]}

def historical_pattern_worker(state: RiskAssessmentState, config: RunnableConfig):
    # Mockup for now as requested
    return _worker_template(state, "historical_pattern_worker", config)

def regulatory_impact_worker(state: RiskAssessmentState, config: RunnableConfig):
    # Mockup for now as requested
    return _worker_template(state, "regulatory_impact_worker", config)

def _worker_template(state: RiskAssessmentState, worker_name: str, config: RunnableConfig) -> Dict[str, Any]:
    # Keeping template for mock workers
    update = {
        "worker_results": [{
            "worker_name": worker_name,
            "score": 5,
            "confidence": 0.9,
            "rationale": f"{worker_name.capitalize()} completed analysis.",
            "flags": []
        }]
    }
    return update

# ─────────────────────────────────────────────────────────────────────────────
# NODE: Orchestrator Monitor
# ─────────────────────────────────────────────────────────────────────────────
def orchestrator_monitor_node(state: RiskAssessmentState, config: RunnableConfig) -> Command:
    thread_id = config["configurable"].get("thread_id")
    log_node_entry("orchestrator_monitor_node", state, thread_id=thread_id)
    
    # Logic to check if we need to re-plan or cancel
    critical_worker = next((r for r in state['worker_results'] if "critical" in r['rationale'].lower()), None)
    
    if critical_worker and not state.get('replan_triggered'):
        # Dynamic re-routing using Command
        log_node_exit("orchestrator_monitor_node (Triggering Replan)", {}, thread_id=thread_id)
        return Command(
            goto="orchestrator_brain",
            update={
                "replan_triggered": True,
                "orchestrator_log": ["Critical findings detected. Triggering re-orchestration."]
            }
        )
    
    log_node_exit("orchestrator_monitor_node", {}, thread_id=thread_id)
    return Command(goto="synthesizer_brain")

# ─────────────────────────────────────────────────────────────────────────────
# NODE: Synthesizer Brain (Bedrock)
# ─────────────────────────────────────────────────────────────────────────────
def synthesizer_brain_node(state: RiskAssessmentState, config: RunnableConfig) -> Dict[str, Any]:
    thread_id = config["configurable"].get("thread_id")
    log_node_entry("synthesizer_brain_node", state, thread_id=thread_id)

    llm = get_llm()
    results_json = json.dumps(state['worker_results'], indent=2)
    prompt = f"""
    You are the Final Synthesizer for a Risk Assessment System.
    Review all worker results and make the final, intelligent risk decision.
    
    COMPLAINT: {state['complaint_description']}
    WORKER RESULTS:
    {results_json}
    
    TASKS:
    1. Calculate the final RPN (Risk Priority Number). Base it on scores (1-10) from severity, occurrence, and detection if available.
    2. Provide a high-level reasoning trail explaining why this risk score was assigned.
    3. Decide if immediate escalation is required.
    
    Return ONLY a JSON object:
    {{
        "rpn": number,
        "escalation_required": boolean,
        "reasoning": "full intelligent analysis",
        "status": "completed | escalated"
    }}
    """
    
    try:
        response = llm.invoke(prompt)
        final_decision = json.loads(response.content)
        update = {
            "rpn_value": final_decision['rpn'],
            "escalation_required": final_decision['escalation_required'],
            "final_reasoning": final_decision['reasoning'],
            "workflow_status": final_decision['status'],
            "scores_valid": True
        }
    except Exception as e:
        log_error("synthesizer_brain_node", e, thread_id=thread_id)
        update = {"errors": [f"Synthesizer Brain Error: {str(e)}"], "workflow_status": "halted"}

    log_node_exit("synthesizer_brain_node", update, thread_id=thread_id)
    return update
