"""
Document Ingestion Agent Nodes
All node functions for the Document Ingestion Agent
"""

import os
import time
from typing import Dict, Any

from .state import AgentState
from .tools.document_detector import detect_document_type, get_file_info, is_supported_format
from .tools.pdf_extractor import extract_text_from_pdf, extract_metadata_from_pdf
from .tools.word_extractor import extract_text_from_word, extract_structured_from_word
from .tools.excel_extractor import extract_text_from_excel, extract_structured_from_excel
from .tools.image_extractor import extract_text_from_image, extract_structured_from_image
from .tools.image_processor import process_embedded_images
from .tools.llm_structurer import structure_document_with_llm, create_fallback_structure
from .logger import (
    log_node_entry, log_node_exit, log_routing_decision, 
    log_error, log_extraction_start, log_extraction_complete
)


def initialize_node(state: AgentState) -> AgentState:
    """
    Node: Initialize state
    Single responsibility: Set up initial state
    """
    log_node_entry("initialize", state)
    
    updates = {
        "iteration": 0,
        "max_iterations": 5,
        "success": False,
        "error_message": None,
        "extracted_text": None,
        "structured_data": None,
        "processing_time": 0.0,
        "error": None,
        "next_step": "detect_type"
    }
    
    log_node_exit("initialize", updates)
    return updates


def detect_type_node(state: AgentState) -> AgentState:
    """
    Node: Detect document type and validate file
    Single responsibility: File validation and type detection
    """
    log_node_entry("detect_type", state)
    
    try:
        file_path = state["file_path"]
        
        # Check if file exists
        if not os.path.exists(file_path):
            error_msg = f"File not found: {file_path}"
            log_error("detect_type", error_msg)
            updates = {
                "error": error_msg,
                "success": False,
                "next_step": "finalize"
            }
            log_routing_decision("detect_type", "finalize", "File not found")
            log_node_exit("detect_type", updates)
            return updates
        
        # Detect document type
        document_type, file_extension = detect_document_type(file_path)
        
        # Check if format is supported
        if not is_supported_format(file_path):
            error_msg = f"Unsupported file format: {file_extension}"
            log_error("detect_type", error_msg)
            updates = {
                "error": error_msg,
                "document_type": document_type,
                "file_extension": file_extension,
                "success": False,
                "next_step": "finalize"
            }
            log_routing_decision("detect_type", "finalize", "Unsupported format")
            log_node_exit("detect_type", updates)
            return updates
        
        # Get file metadata if requested
        file_metadata = {}
        if state.get("include_metadata", True):
            file_metadata = get_file_info(file_path)
            file_metadata["document_type"] = document_type
        
        updates = {
            "document_type": document_type,
            "file_extension": file_extension,
            "file_metadata": file_metadata,
            "next_step": "extract_content"
        }
        
        log_routing_decision("detect_type", "extract_content", f"Detected: {document_type}")
        log_node_exit("detect_type", updates)
        return updates
        
    except Exception as e:
        error_msg = f"Type detection failed: {str(e)}"
        log_error("detect_type", error_msg)
        updates = {
            "error": error_msg,
            "success": False,
            "next_step": "finalize"
        }
        log_routing_decision("detect_type", "finalize", "Exception occurred")
        log_node_exit("detect_type", updates)
        return updates


def extract_content_node(state: AgentState) -> AgentState:
    """
    Node: Extract content from document
    Single responsibility: Content extraction based on document type
    """
    log_node_entry("extract_content", state)
    
    try:
        start_time = time.time()
        
        file_path = state["file_path"]
        document_type = state["document_type"]
        extraction_mode = state.get("extraction_mode", "both")
        
        log_extraction_start(document_type, extraction_mode)
        
        extracted_text = None
        structured_data = None
        
        # Extract based on document type and mode
        if document_type == "pdf":
            if extraction_mode in ["text_only", "both"]:
                extracted_text = extract_text_from_pdf(file_path)
            if extraction_mode in ["structured", "both"]:
                structured_data = extract_metadata_from_pdf(file_path)
                
        elif document_type == "word":
            if extraction_mode in ["text_only", "both"]:
                extracted_text = extract_text_from_word(file_path)
            if extraction_mode in ["structured", "both"]:
                structured_data = extract_structured_from_word(file_path)
                
        elif document_type == "excel":
            if extraction_mode in ["text_only", "both"]:
                extracted_text = extract_text_from_excel(file_path)
            if extraction_mode in ["structured", "both"]:
                structured_data = extract_structured_from_excel(file_path)
                
        elif document_type == "image":
            if extraction_mode in ["text_only", "both"]:
                extracted_text = extract_text_from_image(file_path)
            if extraction_mode in ["structured", "both"]:
                structured_data = extract_structured_from_image(file_path)
        
        else:
            error_msg = f"Extraction not implemented for document type: {document_type}"
            log_error("extract_content", error_msg)
            updates = {
                "error": error_msg,
                "success": False,
                "processing_time": time.time() - start_time,
                "next_step": "finalize"
            }
            log_routing_decision("extract_content", "finalize", "Unsupported type")
            log_node_exit("extract_content", updates)
            return updates
        
        processing_time = time.time() - start_time
        
        # Log extraction results
        text_length = len(extracted_text) if extracted_text else 0
        has_structured = structured_data is not None
        log_extraction_complete(text_length, has_structured)
        
        updates = {
            "extracted_text": extracted_text,
            "structured_data": structured_data,
            "processing_time": processing_time,
            "success": True,
            "next_step": "process_images"
        }
        
        log_routing_decision("extract_content", "process_images", "Extraction complete")
        log_node_exit("extract_content", {"next_step": "process_images", "text_length": text_length, "has_structured": has_structured})
        return updates
        
    except Exception as e:
        error_msg = f"Content extraction failed: {str(e)}"
        log_error("extract_content", error_msg)
        updates = {
            "error": error_msg,
            "error_message": error_msg,
            "success": False,
            "processing_time": time.time() - start_time if 'start_time' in locals() else 0.0,
            "next_step": "process_images"
        }
        log_routing_decision("extract_content", "finalize", "Exception occurred")
        log_node_exit("extract_content", updates)
        return updates


def finalize_node(state: AgentState) -> AgentState:
    """
    Node: Finalize processing
    Single responsibility: Prepare final response
    """
    log_node_entry("finalize", state)
    
    # Set error message if there was an error but no error_message set
    if state.get("error") and not state.get("error_message"):
        updates = {
            "error_message": state["error"],
            "next_step": "end",
            "iteration": state.get("iteration", 0) + 1
        }
    else:
        updates = {
            "next_step": "end",
            "iteration": state.get("iteration", 0) + 1
        }
    
    log_routing_decision("finalize", "END", "Process complete")
    log_node_exit("finalize", updates)
    return updates


def process_images_node(state: AgentState) -> AgentState:
    """
    Node: Process embedded images with OCR
    Single responsibility: Extract text from embedded images
    """
    log_node_entry("process_images", state)
    
    try:
        file_path = state["file_path"]
        document_type = state["document_type"]
        
        # Only process images for PDF and Word documents
        if document_type in ["pdf", "word"]:
            ocr_data = process_embedded_images(file_path, document_type)
        else:
            ocr_data = {
                "total_images": 0,
                "images_with_text": 0,
                "ocr_results": []
            }
        
        # Check if LLM structuring is requested
        use_llm = state.get("use_llm_structuring", True)
        next_step = "structure_with_llm" if use_llm else "finalize"
        
        updates = {
            "ocr_data": ocr_data,
            "next_step": next_step
        }
        
        log_routing_decision("process_images", next_step, f"Found {ocr_data['images_with_text']} images with text")
        log_node_exit("process_images", {"next_step": next_step, "images_processed": ocr_data["total_images"]})
        return updates
        
    except Exception as e:
        error_msg = f"Image processing failed: {str(e)}"
        log_error("process_images", error_msg)
        
        # Continue to next step even if image processing fails
        use_llm = state.get("use_llm_structuring", True)
        next_step = "structure_with_llm" if use_llm else "finalize"
        
        updates = {
            "ocr_data": {"total_images": 0, "images_with_text": 0, "ocr_results": [], "error": error_msg},
            "next_step": next_step
        }
        log_routing_decision("process_images", next_step, "Image processing failed, continuing")
        log_node_exit("process_images", updates)
        return updates


def structure_with_llm_node(state: AgentState) -> AgentState:
    """
    Node: Structure document using LLM
    Single responsibility: Convert extracted text to structured JSON using LLM
    """
    log_node_entry("structure_with_llm", state)
    
    try:
        extracted_text = state.get("extracted_text", "")
        ocr_data = state.get("ocr_data", {})
        
        # Combine OCR text from embedded images
        ocr_text = ""
        if ocr_data and ocr_data.get("ocr_results"):
            ocr_texts = [result["ocr_text"] for result in ocr_data["ocr_results"]]
            ocr_text = "\n\n".join(ocr_texts)
        
        if not extracted_text.strip():
            error_msg = "No text available for LLM structuring"
            log_error("structure_with_llm", error_msg)
            updates = {
                "llm_structured_data": None,
                "next_step": "finalize"
            }
            log_routing_decision("structure_with_llm", "finalize", "No text to structure")
            log_node_exit("structure_with_llm", updates)
            return updates
        
        # Use LLM to structure the document
        llm_structured_data = structure_document_with_llm(extracted_text, ocr_text)
        
        # If LLM structuring failed, create fallback structure
        if llm_structured_data.get("error"):
            document_type = state.get("document_type", "unknown")
            llm_structured_data = create_fallback_structure(extracted_text, document_type)
        
        updates = {
            "llm_structured_data": llm_structured_data,
            "next_step": "finalize"
        }
        
        log_routing_decision("structure_with_llm", "finalize", "LLM structuring complete")
        log_node_exit("structure_with_llm", {"next_step": "finalize", "structured": bool(llm_structured_data)})
        return updates
        
    except Exception as e:
        error_msg = f"LLM structuring failed: {str(e)}"
        log_error("structure_with_llm", error_msg)
        
        # Create fallback structure
        extracted_text = state.get("extracted_text", "")
        document_type = state.get("document_type", "unknown")
        fallback_structure = create_fallback_structure(extracted_text, document_type)
        
        updates = {
            "llm_structured_data": fallback_structure,
            "next_step": "finalize"
        }
        log_routing_decision("structure_with_llm", "finalize", "Using fallback structure")
        log_node_exit("structure_with_llm", updates)
        return updates