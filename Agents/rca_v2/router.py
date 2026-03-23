"""
RCA v2 Orchestrator API Router
Handles all RCA v2 orchestrator endpoints with proper state machine
"""
from fastapi import APIRouter, HTTPException, File, UploadFile, Form
from typing import Optional
import os
import tempfile
from .schemas import WhyAnalysisInput, WhyAnalysisOutput
from .logger import log_api_request, log_api_response, log_error, log_orchestrator_start, log_orchestrator_complete
from .agent_integrated import RCAOrchestratorV2Integrated

# ---------------------------------------------------------------------------
# Router setup
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/rca-v2", tags=["rca-v2-orchestrator"])

# Lazy singleton
_orchestrator: RCAOrchestratorV2Integrated = None

def _get_orchestrator() -> RCAOrchestratorV2Integrated:
    """Return the singleton orchestrator, creating it if necessary."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = RCAOrchestratorV2Integrated()
    return _orchestrator
# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/", response_model=WhyAnalysisOutput)
def run_rca_analysis_json(input_data: WhyAnalysisInput):
    """
    Run complete RCA v2 Analysis to find the root cause (JSON input).
    
    This endpoint uses proper state machine implementation with:
    - Central JSON state object
    - Controlled LLM context (no full history)
    - Orchestrator-only memory updates
    - Separate execution + control memory
    - Proper state machine transitions
    
    **Input (JSON):**
    - `complaint_id` : Unique CAPA/complaint record ID
    - `complaint`    : The problem statement
    - `evidence`     : *(optional)* Supporting facts
    - `sop`          : *(optional)* Relevant SOP
    - `fmea_document_path` : *(optional)* Path to FMEA Excel file
    - `max_depth`    : *(optional)* Maximum iterations (default: 5)
    """
    try:
        orchestrator = _get_orchestrator()
        
        # Log orchestrator start
        log_orchestrator_start(
            input_data.complaint_id,
            "FMEA_ITERATIVE" if input_data.fmea_document_path else "NO_FMEA_SINGLE_SHOT",
            input_data.max_depth or 5
        )
        
        # Log request
        log_api_request(
            "/rca-v2",
            input_data.complaint_id,
            has_fmea=bool(input_data.fmea_document_path),
        )
        
        # Run analysis
        result = orchestrator.analyze(input_data)
        
        # Log completion
        log_orchestrator_complete(
            input_data.complaint_id,
            result.get("analysis_depth", 0),
            bool(result.get("root_cause")),
            result.get("execution_time_seconds", 0.0)
        )
        
        # Check for complete failure
        if result.get("error") and result.get("root_cause") is None and result.get("analysis_depth", 0) == 0:
            log_error("router /rca-v2", result["error"])
            
            # Check if it's a validation error (400) vs system error (500)
            if result.get("mode") == "VALIDATION_ERROR":
                raise HTTPException(status_code=400, detail=result["error"])
            else:
                raise HTTPException(status_code=500, detail=result["error"])
        
        # Log response
        root_cause_id = None
        if result.get("root_cause"):
            root_cause_id = result["root_cause"].get("cause_id")
        log_api_response(
            input_data.complaint_id,
            root_cause_id=root_cause_id,
            depth=result.get("analysis_depth", 0),
            mode=result.get("mode", ""),
        )
        
        return WhyAnalysisOutput(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        log_error("router /rca-v2", str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Error running RCA v2 Analysis: {str(e)}",
        )


@router.post("/upload", response_model=WhyAnalysisOutput)
async def run_rca_analysis(
    complaint_id: str = Form(...),
    complaint: str = Form(...),
    evidence: Optional[str] = Form(""),
    sop: Optional[str] = Form(""),
    fmea_document_path: Optional[str] = Form(None),
    fmea_file: Optional[UploadFile] = File(None),
    max_depth: Optional[int] = Form(5)
):
    """
    Run complete RCA v2 Analysis to find the root cause.
    
    This endpoint uses proper state machine implementation with:
    - Central JSON state object (RCAStateMachine)
    - Controlled LLM context (no full conversation history)
    - Orchestrator-only memory updates (LLM never updates memory)
    - Separate execution + control memory
    - Proper state machine transitions with validation
    
    **Key Improvements over v1:**
    - ✅ Central JSON state object
    - ✅ Always pass controlled context (not full history) to LLM
    - ✅ Let orchestrator (not LLM) update memory
    - ✅ Keep execution memory + control memory separate
    - ✅ Treat system like a state machine
    
    **Input (Form Data):**
    - `complaint_id` : Unique CAPA/complaint record ID
    - `complaint`    : The problem statement
    - `evidence`     : *(optional)* Supporting facts, observations, measurements
    - `sop`          : *(optional)* Relevant Standard Operating Procedure
    - `fmea_file`    : *(optional)* FMEA Excel file upload
    - `fmea_document_path` : *(optional)* Path to FMEA Excel file (used if fmea_file not provided)
    - `max_depth`    : *(optional)* Maximum iterations (default: 5)
    
    **Output:**
    - Complete analysis with state machine tracking
    - Detailed iteration information
    - State transition logs
    - Controlled memory management
    """
    temp_file_path = None
    
    try:
        orchestrator = _get_orchestrator()
        
        # Handle FMEA file upload or path
        final_fmea_path = None
        
        if fmea_file:
            # Save uploaded file to temporary location
            temp_file_path = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx").name
            
            with open(temp_file_path, "wb") as f:
                content = await fmea_file.read()
                f.write(content)
            
            final_fmea_path = temp_file_path
            
        elif fmea_document_path:
            # Use provided file path
            final_fmea_path = fmea_document_path
        
        # Create input object
        input_data = WhyAnalysisInput(
            complaint_id=complaint_id,
            complaint=complaint,
            evidence=evidence,
            sop=sop,
            fmea_document_path=final_fmea_path,
            max_depth=max_depth
        )
        
        # Log orchestrator start
        log_orchestrator_start(
            input_data.complaint_id,
            "FMEA_ITERATIVE" if final_fmea_path else "NO_FMEA_SINGLE_SHOT",
            input_data.max_depth or 5
        )
        
        # Log request
        log_api_request(
            "/rca-v2",
            input_data.complaint_id,
            has_fmea=bool(final_fmea_path),
        )
        
        # Run analysis
        result = orchestrator.analyze(input_data)
        
        # Log completion
        log_orchestrator_complete(
            input_data.complaint_id,
            result.get("analysis_depth", 0),
            bool(result.get("root_cause")),
            result.get("execution_time_seconds", 0.0)
        )
        
        # Check for complete failure (only if analysis didn't even start)
        if result.get("error") and result.get("root_cause") is None and result.get("analysis_depth", 0) == 0:
            log_error("router /rca-v2", result["error"])
            
            # Check if it's a validation error (400) vs system error (500)
            if result.get("mode") == "VALIDATION_ERROR":
                raise HTTPException(status_code=400, detail=result["error"])
            else:
                raise HTTPException(status_code=500, detail=result["error"])
        
        # Log response
        root_cause_id = None
        if result.get("root_cause"):
            root_cause_id = result["root_cause"].get("cause_id")
        log_api_response(
            input_data.complaint_id,
            root_cause_id=root_cause_id,
            depth=result.get("analysis_depth", 0),
            mode=result.get("mode", ""),
        )
        
        # Return result directly (already in correct format)
        return WhyAnalysisOutput(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        log_error("router /rca-v2", str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Error running RCA v2 Analysis: {str(e)}",
        )
    finally:
        # Clean up temporary file if it was created
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except:
                pass  # Ignore cleanup errors
@router.get("/health")
def rca_v2_health():
    """Health check for the RCA v2 Orchestrator."""
    return {
        "status": "healthy",
        "agent": "rca_v2_orchestrator",
        "description": "RCA v2 with proper state machine implementation",
        "modes": ["FMEA_ITERATIVE", "NO_FMEA_SINGLE_SHOT"],
        "improvements": [
            "Central JSON state object (RCAStateMachine)",
            "Controlled LLM context (no full history)",
            "Orchestrator-only memory updates",
            "Separate execution + control memory",
            "Proper state machine transitions",
            "State validation and error handling"
        ],
        "features": [
            "No Redis dependency",
            "Comprehensive error handling",
            "Detailed iteration tracking",
            "Execution time monitoring",
            "Works with or without FMEA",
            "State machine with defined transitions",
            "Memory separation and control"
        ]
    }
