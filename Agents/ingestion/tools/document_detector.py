"""
Document Type Detector
Detects document type and routes to appropriate extractor
"""

import os
from pathlib import Path
from typing import Tuple, Dict, Any


def detect_document_type(file_path: str) -> Tuple[str, str]:
    """
    Detect document type based on file extension
    
    Args:
        file_path: Path to document file
        
    Returns:
        Tuple of (document_type, file_extension)
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    file_extension = Path(file_path).suffix.lower()
    
    # Map extensions to document types
    type_mapping = {
        '.pdf': 'pdf',
        '.docx': 'word',
        '.doc': 'word',
        '.xlsx': 'excel',
        '.xls': 'excel',
        '.csv': 'csv',
        '.jpg': 'image',
        '.jpeg': 'image',
        '.png': 'image',
        '.bmp': 'image',
        '.tiff': 'image',
        '.tif': 'image'
    }
    
    document_type = type_mapping.get(file_extension, 'unknown')
    
    return document_type, file_extension


def get_file_info(file_path: str) -> Dict[str, Any]:
    """
    Get basic file information
    
    Args:
        file_path: Path to file
        
    Returns:
        Dictionary with file metadata
    """
    try:
        stat = os.stat(file_path)
        path_obj = Path(file_path)
        
        return {
            "file_name": path_obj.name,
            "file_size": stat.st_size,
            "file_extension": path_obj.suffix.lower(),
            "created_time": stat.st_ctime,
            "modified_time": stat.st_mtime,
            "absolute_path": os.path.abspath(file_path)
        }
        
    except Exception as e:
        return {"error": str(e)}


def is_supported_format(file_path: str) -> bool:
    """
    Check if file format is supported for extraction
    
    Args:
        file_path: Path to file
        
    Returns:
        True if supported, False otherwise
    """
    document_type, _ = detect_document_type(file_path)
    return document_type != 'unknown'


def get_supported_formats() -> Dict[str, list]:
    """
    Get list of supported file formats by category
    
    Returns:
        Dictionary mapping document types to supported extensions
    """
    return {
        "pdf": [".pdf"],
        "word": [".docx", ".doc"],
        "excel": [".xlsx", ".xls"],
        "csv": [".csv"],
        "image": [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"]
    }