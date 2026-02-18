"""
Word Document Extractor Tool
Extracts raw text from Word documents (.docx).
"""

from typing import Optional
from docx import Document


def extract_text_from_word(file_path: str) -> Optional[str]:
    """
    Extract raw text from Word document.
    
    Args:
        file_path: Path to Word document (.docx)
        
    Returns:
        Extracted text as string, or None if extraction fails
        
    Raises:
        FileNotFoundError: If file doesn't exist
        Exception: If Word parsing fails
    """
    
    try:
        doc = Document(file_path)
        
        text_parts = []
        
        # Extract text from paragraphs
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_parts.append(paragraph.text)
        
        # Extract text from tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        text_parts.append(cell.text)
        
        full_text = "\n".join(text_parts)
        
        if not full_text.strip():
            return None
        
        return full_text
        
    except FileNotFoundError:
        raise FileNotFoundError(f"Word document not found: {file_path}")
    except Exception as e:
        raise Exception(f"Failed to extract text from Word document: {str(e)}")
