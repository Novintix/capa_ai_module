from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from typing import List
from Agents.categorize.state import CategorizeInput, CategorizeOutput, Cause
from Agents.categorize.graph import categorize_graph
from Agents.categorize.logger import log_request, log_final_output, log_error

router = APIRouter(prefix="/categorize", tags=["categorize"])


@router.post("/analyze", response_model=CategorizeOutput)
async def categorize_causes_endpoint(request: CategorizeInput):
    """
    Categorize root causes into 6M categories (Fishbone Diagram).
    
    Accepts:
    - question: The original question being analyzed
    - causes: List of causes to categorize
    - additional_context: Optional context
    
    Returns:
    - Categorized causes with 6M category assignments and summary statistics
    """
    try:
        log_request(
            question=request.question,
            num_causes=len(request.causes)
        )
        
        # Validate input
        if not request.causes:
            raise HTTPException(status_code=400, detail="causes list cannot be empty")
        
        # Initialize state
        initial_state = {
            "input": request,
            "iteration": 0,
            "raw_categorizations": None,
            "final_output": None
        }
        
        # Invoke graph
        result = categorize_graph.invoke(initial_state)
        final_output = result.get("final_output")
        
        if not final_output:
            raise ValueError("Agent failed to produce a final output.")
        
        log_final_output(summary=final_output.summary)
        
        return JSONResponse(content={
            "categorized_causes": [c.model_dump() for c in final_output.categorized_causes],
            "summary": final_output.summary
        })
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = f"Error processing categorization: {str(e)}\n{traceback.format_exc()}"
        log_error("router", error_detail)
        raise HTTPException(status_code=500, detail=f"Error processing categorization: {str(e)}")
