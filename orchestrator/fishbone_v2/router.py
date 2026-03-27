"""
Fishbone v2 Orchestrator API Router
FastAPI endpoints for single-depth fishbone analysis
"""

from fastapi import APIRouter, HTTPException, File, UploadFile, Form
from typing import Optional
import os
import tempfile
from .schemas import FishboneInput, FishboneOutput
from .logger import log_api_request, log_api_response, log_error
from .agent import FishboneOrchestratorV2

router = APIRouter(prefix="/fishbone-v2", tags=["fishbone-v2-orchestrator"])

# Lazy singleton
_orchestrator: FishboneOrchestratorV2 = None

def _get_orchestrator() -> FishboneOrchestratorV2:
    """Return the singleton orchestrator"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = FishboneOrchestratorV2()
    return _orchestrator


@router.post("/", response_model=FishboneOutput)
def run_fishbone_analysis_json(input_data: FishboneInput):
    """
    Run Fishbone v2 Analysis - Single Depth with 6M Categorization (JSON input)
    
    Flow:
    1. List Causes Agent → Generate causes from complaint
    2. Categorization Agent → Classify into 6M categories
    3. Validation Agent → Validate against evidence
    4. Decision Router:
       - 0 validated → Zero Evidence Agent
       - 1 validated → Select and complete
       - >1 validated → Ranking Agent
    
    Input (JSON):
    - complaint_id: Unique identifier
    - complaint: Problem description
    - evidence: (optional) Supporting facts
    - sop: (optional) Standard Operating Procedure
    - fmea_document_path: (optional) Path to FMEA Excel file
    - evidence_files: (optional) List of evidence file paths
    
    Output:
    - root_cause: Selected root cause with 6M category
    - causes: All causes with categorization and validation
    - category_summary: Count per 6M category
    - confidence: Overall confidence level
    """
    try:
        orchestrator = _get_orchestrator()
        
        log_api_request(
            "/fishbone-v2",
            input_data.complaint_id,
            has_fmea=bool(input_data.fmea_document_path)
        )
        
        # Run analysis
        result = orchestrator.analyze(input_data)
        
        # Check for validation error
        if result.get("error") and result.get("mode") == "VALIDATION_ERROR":
            log_error("router /fishbone-v2", result["error"])
            raise HTTPException(status_code=400, detail=result["error"])
        
        # Check for system error
        if result.get("error") and result.get("root_cause") is None:
            log_error("router /fishbone-v2", result["error"])
            raise HTTPException(status_code=500, detail=result["error"])
        
        # Log response
        root_cause_id = None
        if result.get("root_cause"):
            root_cause_id = result["root_cause"].get("cause_id")
        
        log_api_response(
            input_data.complaint_id,
            root_cause_id=root_cause_id,
            depth=1,
            mode=result.get("mode", "")
        )
        
        return FishboneOutput(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        log_error("router /fishbone-v2", str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Error running Fishbone v2 Analysis: {str(e)}"
        )


@router.post("/upload", response_model=FishboneOutput)
async def run_fishbone_analysis_upload(
    complaint_id: str = Form(...),
    complaint: str = Form(...),
    evidence: Optional[str] = Form(""),
    sop: Optional[str] = Form(""),
    fmea_document_path: Optional[str] = Form(None),
    fmea_file: Optional[UploadFile] = File(None)
):
    """
    Run Fishbone v2 Analysis with file upload support
    
    Supports FMEA file upload via multipart/form-data
    """
    temp_file_path = None
    
    try:
        orchestrator = _get_orchestrator()
        
        # Handle FMEA file upload
        final_fmea_path = None
        
        if fmea_file:
            temp_file_path = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx").name
            
            with open(temp_file_path, "wb") as f:
                content = await fmea_file.read()
                f.write(content)
            
            final_fmea_path = temp_file_path
            
        elif fmea_document_path:
            final_fmea_path = fmea_document_path
        
        # Create input object
        input_data = FishboneInput(
            complaint_id=complaint_id,
            complaint=complaint,
            evidence=evidence,
            sop=sop,
            fmea_document_path=final_fmea_path
        )
        
        log_api_request(
            "/fishbone-v2/upload",
            input_data.complaint_id,
            has_fmea=bool(final_fmea_path)
        )
        
        # Run analysis
        result = orchestrator.analyze(input_data)
        
        # Check for errors
        if result.get("error") and result.get("mode") == "VALIDATION_ERROR":
            log_error("router /fishbone-v2/upload", result["error"])
            raise HTTPException(status_code=400, detail=result["error"])
        
        if result.get("error") and result.get("root_cause") is None:
            log_error("router /fishbone-v2/upload", result["error"])
            raise HTTPException(status_code=500, detail=result["error"])
        
        # Log response
        root_cause_id = None
        if result.get("root_cause"):
            root_cause_id = result["root_cause"].get("cause_id")
        
        log_api_response(
            input_data.complaint_id,
            root_cause_id=root_cause_id,
            depth=1,
            mode=result.get("mode", "")
        )
        
        return FishboneOutput(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        log_error("router /fishbone-v2/upload", str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Error running Fishbone v2 Analysis: {str(e)}"
        )
    finally:
        # Clean up temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except:
                pass


@router.get("/health")
def fishbone_v2_health():
    """Health check for Fishbone v2 Orchestrator"""
    return {
        "status": "healthy",
        "agent": "fishbone_v2_orchestrator",
        "description": "Single-depth fishbone analysis with 6M categorization",
        "mode": "SINGLE_SHOT",
        "features": [
            "Direct cause generation from complaint",
            "6M categorization (Man, Machine, Method, Material, Measurement, Environment)",
            "Evidence-based validation",
            "Confidence-based routing",
            "Redis session management",
            "Production-grade error handling"
        ]
    }
