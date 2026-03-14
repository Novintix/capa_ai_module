"""
Word Document Extractor
Extracts text from Word (.docx, .doc) files
"""

import docx
from typing import Dict, Any, List


def extract_text_from_word(file_path: str) -> str:
    """
    Extract text content from Word file
    
    Args:
        file_path: Path to Word file
        
    Returns:
        Extracted text as string
    """
    try:
        doc = docx.Document(file_path)
        
        # Extract paragraphs
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        
        # Extract tables
        table_text = []
        for table in doc.tables:
            for row in table.rows:
                row_text = [cell.text for cell in row.cells]
                table_text.append(" | ".join(row_text))
        
        # Combine all text
        all_text = "\n".join(paragraphs)
        if table_text:
            all_text += "\n\nTables:\n" + "\n".join(table_text)
        
        return all_text.strip()
        
    except Exception as e:
        raise Exception(f"Failed to extract text from Word: {str(e)}")


def extract_structured_from_word(file_path: str) -> Dict[str, Any]:
    """
    Extract structured content from Word file
    
    Args:
        file_path: Path to Word file
        
    Returns:
        Dictionary with structured content
    """
    try:
        doc = docx.Document(file_path)
        
        # Extract paragraphs with styles
        paragraphs = []
        for para in doc.paragraphs:
            if para.text.strip():
                paragraphs.append({
                    "text": para.text,
                    "style": para.style.name
                })
        
        # Extract tables
        tables = []
        for table in doc.tables:
            table_data = []
            for row in table.rows:
                row_data = [cell.text for cell in row.cells]
                table_data.append(row_data)
            tables.append(table_data)
        
        return {
            "paragraphs": paragraphs,
            "tables": tables,
            "num_paragraphs": len(paragraphs),
            "num_tables": len(tables)
        }
        
    except Exception as e:
        raise Exception(f"Failed to extract structured content from Word: {str(e)}")
