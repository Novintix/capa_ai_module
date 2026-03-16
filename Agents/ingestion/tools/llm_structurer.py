"""
LLM-based Document Structuring
Uses AWS Bedrock to convert extracted text into structured JSON
"""

import json
import re
from typing import Dict, Any
from config.aws_bedrock_config import get_llm


# Prompts for different document types
STRUCTURE_SYSTEM_PROMPT = """You are a document structuring expert. Your task is to analyze extracted text and convert it into a well-structured JSON format.

RULES:
1. Return ONLY valid JSON - no explanations or markdown
2. Identify document sections, headers, tables, lists
3. Preserve important data relationships
4. Use consistent field naming (snake_case)
5. Include metadata about document structure
6. Handle OCR errors gracefully

OUTPUT FORMAT:
{
  "document_type": "detected_type",
  "title": "document_title",
  "sections": [
    {
      "section_name": "string",
      "content": "string",
      "subsections": []
    }
  ],
  "tables": [
    {
      "table_name": "string",
      "headers": ["col1", "col2"],
      "rows": [["val1", "val2"]]
    }
  ],
  "key_data": {
    "extracted_fields": "values"
  },
  "metadata": {
    "total_sections": 0,
    "total_tables": 0,
    "confidence": 0.0
  }
}"""

FMEA_STRUCTURE_PROMPT = """You are analyzing an FMEA (Failure Mode and Effects Analysis) document. Structure it into standard FMEA format:

{
  "document_type": "fmea",
  "title": "FMEA Title",
  "process_steps": [
    {
      "step_name": "Process Step",
      "potential_failure_modes": [
        {
          "failure_mode": "What can go wrong",
          "potential_effects": "Impact on customer",
          "severity": 1-10,
          "potential_causes": "Why it happens",
          "occurrence": 1-10,
          "current_controls": "Existing controls",
          "detection": 1-10,
          "rpn": "calculated_value",
          "recommended_actions": "Improvements"
        }
      ]
    }
  ],
  "metadata": {
    "total_process_steps": 0,
    "total_failure_modes": 0,
    "highest_rpn": 0
  }
}"""

POLICY_STRUCTURE_PROMPT = """You are analyzing a policy/procedure document. Structure it into standard policy format:

{
  "document_type": "policy",
  "title": "Policy Title",
  "policy_number": "Policy ID",
  "version": "Version",
  "effective_date": "Date",
  "sections": [
    {
      "section_number": "1.0",
      "section_title": "Purpose",
      "content": "Section content",
      "requirements": ["requirement1", "requirement2"],
      "procedures": [
        {
          "step_number": "1.1",
          "description": "Step description",
          "responsible_party": "Who does it"
        }
      ]
    }
  ],
  "definitions": {
    "term": "definition"
  },
  "references": ["ref1", "ref2"]
}"""


def clean_llm_response(response_text: str) -> str:
    """Clean LLM response by removing reasoning tags and markdown"""
    # Strip reasoning tags if present
    if "<reasoning>" in response_text and "</reasoning>" in response_text:
        response_text = re.sub(r'<reasoning>.*?</reasoning>\s*', '', response_text, flags=re.DOTALL).strip()
    
    # Remove markdown code blocks
    response_text = response_text.replace('```json', '').replace('```', '').strip()
    
    # Extract JSON object - find first { and last }
    start_idx = response_text.find('{')
    end_idx = response_text.rfind('}')
    
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        response_text = response_text[start_idx:end_idx+1]
    else:
        raise ValueError(f"No valid JSON object found in response")
    
    return response_text


def detect_document_type_from_text(text: str) -> str:
    """
    Detect document type from extracted text content
    
    Args:
        text: Extracted text content
        
    Returns:
        Detected document type
    """
    text_lower = text.lower()
    
    # FMEA indicators
    fmea_keywords = ['failure mode', 'severity', 'occurrence', 'detection', 'rpn', 'fmea', 'potential effect']
    if sum(1 for keyword in fmea_keywords if keyword in text_lower) >= 3:
        return "fmea"
    
    # Policy indicators
    policy_keywords = ['policy', 'procedure', 'section', 'requirement', 'shall', 'must', 'compliance']
    if sum(1 for keyword in policy_keywords if keyword in text_lower) >= 3:
        return "policy"
    
    # SOP indicators
    sop_keywords = ['standard operating procedure', 'sop', 'step', 'instruction', 'method']
    if sum(1 for keyword in sop_keywords if keyword in text_lower) >= 2:
        return "sop"
    
    # Report indicators
    report_keywords = ['report', 'analysis', 'findings', 'conclusion', 'recommendation']
    if sum(1 for keyword in report_keywords if keyword in text_lower) >= 2:
        return "report"
    
    return "general"


def structure_document_with_llm(extracted_text: str, ocr_text: str = "") -> Dict[str, Any]:
    """
    Use LLM to structure document text into JSON format
    
    Args:
        extracted_text: Main document text
        ocr_text: Text from embedded images (OCR)
        
    Returns:
        Structured JSON data
    """
    try:
        # Initialize LLM
        llm = get_llm()
        
        # Combine all text
        full_text = extracted_text
        if ocr_text.strip():
            full_text += f"\n\n--- TEXT FROM EMBEDDED IMAGES ---\n{ocr_text}"
        
        # Detect document type
        doc_type = detect_document_type_from_text(full_text)
        
        # Choose appropriate prompt
        if doc_type == "fmea":
            system_prompt = FMEA_STRUCTURE_PROMPT
        elif doc_type == "policy":
            system_prompt = POLICY_STRUCTURE_PROMPT
        else:
            system_prompt = STRUCTURE_SYSTEM_PROMPT
        
        # Build user prompt
        user_prompt = f"""Analyze and structure this document text:

DOCUMENT TEXT:
{full_text[:8000]}  # Limit to avoid token limits

Convert this into the specified JSON structure. Focus on extracting key information and maintaining data relationships."""
        
        # Combine prompts
        full_prompt = system_prompt + "\n\n" + user_prompt
        
        # Call LLM
        response = llm.invoke(full_prompt)
        response_text = clean_llm_response(response.content)
        
        # Parse JSON
        structured_data = json.loads(response_text)
        
        # Add processing metadata
        structured_data["processing_metadata"] = {
            "detected_document_type": doc_type,
            "has_ocr_content": bool(ocr_text.strip()),
            "text_length": len(full_text),
            "processing_method": "llm_structured"
        }
        
        return structured_data
        
    except json.JSONDecodeError as e:
        return {
            "document_type": "unknown",
            "error": f"JSON parsing failed: {str(e)}",
            "raw_response": response_text if 'response_text' in locals() else "",
            "processing_metadata": {
                "processing_method": "llm_structured",
                "success": False
            }
        }
    except Exception as e:
        return {
            "document_type": "unknown",
            "error": f"LLM structuring failed: {str(e)}",
            "processing_metadata": {
                "processing_method": "llm_structured",
                "success": False
            }
        }


def create_fallback_structure(extracted_text: str, document_type: str) -> Dict[str, Any]:
    """
    Create basic structure when LLM fails
    
    Args:
        extracted_text: Document text
        document_type: Detected document type
        
    Returns:
        Basic structured format
    """
    # Split text into paragraphs
    paragraphs = [p.strip() for p in extracted_text.split('\n\n') if p.strip()]
    
    # Try to identify title (first non-empty line)
    title = paragraphs[0] if paragraphs else "Untitled Document"
    
    return {
        "document_type": document_type,
        "title": title,
        "content": {
            "paragraphs": paragraphs,
            "total_paragraphs": len(paragraphs)
        },
        "processing_metadata": {
            "processing_method": "fallback_structure",
            "success": True
        }
    }