"""
PDF Document Extractor
Extracts text from PDF files
"""

import PyPDF2
from typing import Dict, Any


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract text content from PDF file
    
    Args:
        file_path: Path to PDF file
        
    Returns:
        Extracted text as string
    """
    try:
        text = ""
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            num_pages = len(pdf_reader.pages)
            
            for page_num in range(num_pages):
                page = pdf_reader.pages[page_num]
                text += page.extract_text()
        
        return text.strip()
        
    except Exception as e:
        raise Exception(f"Failed to extract text from PDF: {str(e)}")


def extract_metadata_from_pdf(file_path: str) -> Dict[str, Any]:
    """
    Extract metadata from PDF file
    
    Args:
        file_path: Path to PDF file
        
    Returns:
        Dictionary with metadata
    """
    try:
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            metadata = pdf_reader.metadata
            
            return {
                "title": metadata.get('/Title', ''),
                "author": metadata.get('/Author', ''),
                "subject": metadata.get('/Subject', ''),
                "creator": metadata.get('/Creator', ''),
                "producer": metadata.get('/Producer', ''),
                "creation_date": metadata.get('/CreationDate', ''),
                "num_pages": len(pdf_reader.pages)
            }
            
    except Exception as e:
        return {"error": str(e)}
