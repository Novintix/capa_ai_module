"""
Document Ingestion Agent API Router
Handles all document ingestion endpoints
"""

import os
from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import List

from .schemas import DocumentInput, ExtractionResult, BatchDocumentInput, BatchExtractionResult, ExtractionMode
from .logger import log_api_request, log_api_response
from .agent import DocumentIngestionAgent


# Create API router
router = APIRouter(prefix="/ingestion", tags=["ingestion"])

# Lazy initialization of agent
_ingestion_agent = None


def get_ingestion_agent():
    """Get or initialize the document ingestion agent (lazy initialization)"""
    global _ingestion_agent
    if _ingestion_agent is None:
        _ingestion_agent = DocumentIngestionAgent()
    return _ingestion_agent


@router.post("/", response_model=ExtractionResult)
def extract_document(document: DocumentInput):
    """
    Extract content from a single document with advanced processing capabilities
    
    Supports multiple document types:
    - PDF (.pdf) - includes embedded image extraction and OCR
    - Word (.docx, .doc) - includes embedded image extraction and OCR
    - Excel (.xlsx, .xls)
    - Images (.jpg, .jpeg, .png, .bmp, .tiff, .tif)
    
    Extraction modes:
    - text_only: Extract only text content
    - structured: Extract structured data (tables, metadata)
    - both: Extract both text and structured data
    
    Advanced Features:
    - LLM Structuring: Uses AWS Bedrock to intelligently structure extracted text into JSON
    - Embedded Image OCR: Extracts and processes images within PDF/Word documents using Azure Vision
    - Document Type Detection: Automatically detects FMEA, Policy, SOP, Report formats for optimal structuring
    - Semantic Analysis: Identifies document sections, tables, key data relationships
    
    Args:
        document: Document input with file path and extraction settings
        
    Returns:
        ExtractionResult with extracted content, structured data, LLM analysis, and OCR results
    """
    
    try:
        # Get agent (lazy initialization)
        ingestion_agent = get_ingestion_agent()
        
        # Log request
        log_api_request("/ingestion", document.document_id, document.file_path)
        
        # Check if file exists
        if not os.path.exists(document.file_path):
            raise HTTPException(
                status_code=404,
                detail=f"Document not found: {document.file_path}"
            )
        
        # Process document
        result = ingestion_agent.process_document(document)
        
        # Log response
        log_api_response(document.document_id, result["success"], result["processing_time"])
        
        return ExtractionResult(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing document: {str(e)}"
        )


@router.post("/batch", response_model=BatchExtractionResult)
def extract_batch(batch: BatchDocumentInput):
    """
    Extract content from multiple documents in batch with advanced processing
    
    Processes multiple documents with the same extraction settings.
    Includes all advanced features: LLM structuring, embedded image OCR, and intelligent document analysis.
    
    Args:
        batch: Batch input with list of file paths and extraction settings
        
    Returns:
        BatchExtractionResult with comprehensive results for all documents
    """
    
    try:
        # Get agent (lazy initialization)
        ingestion_agent = get_ingestion_agent()
        
        # Log request
        log_api_request("/ingestion/batch", batch.batch_id, f"{len(batch.file_paths)} files")
        
        # Process batch
        result = ingestion_agent.process_batch(batch)
        
        # Log response
        log_api_response(batch.batch_id, result["successful_extractions"] > 0, result["total_processing_time"])
        
        return BatchExtractionResult(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing batch: {str(e)}"
        )


@router.get("/supported-formats")
def get_supported_formats():
    """Get list of supported document formats"""
    from .tools.document_detector import get_supported_formats
    
    return {
        "supported_formats": get_supported_formats(),
        "extraction_modes": [mode.value for mode in ExtractionMode]
    }


@router.get("/health")
def ingestion_health():
    """Document ingestion agent health check"""
    ingestion_agent = get_ingestion_agent()
    
    # Check Azure OCR credentials
    azure_key_present = bool(os.getenv("AZURE_VISION_KEY"))
    azure_endpoint_present = bool(os.getenv("AZURE_VISION_ENDPOINT"))
    
    # Check AWS Bedrock availability
    try:
        from config.aws_bedrock_config import get_llm
        llm = get_llm()
        aws_bedrock_available = True
    except:
        aws_bedrock_available = False
    
    return {
        "status": "healthy",
        "agent": "ingestion",
        "agent_initialized": ingestion_agent is not None,
        "azure_ocr_configured": azure_key_present and azure_endpoint_present,
        "aws_bedrock_available": aws_bedrock_available,
        "supported_formats": ["pdf", "word", "excel", "image"],
        "advanced_features": {
            "llm_structuring": aws_bedrock_available,
            "embedded_image_ocr": azure_key_present and azure_endpoint_present,
            "document_type_detection": True,
            "semantic_analysis": True
        }
    }