"""
Word Extractor Tool
Extracts text from .docx files for supporting evidence ingestion.
"""

from typing import Optional
from docx import Document


def extract_text_from_word(file_path: str) -> Optional[str]:
    """
    Extract raw text from a Word document (.docx).

    Args:
        file_path: Path to the Word document

    Returns:
        Extracted text as string, or None if empty

    Raises:
        FileNotFoundError: If file doesn't exist
        Exception: If Word parsing fails
    """
    try:
        doc = Document(file_path)
        text_parts = []

        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_parts.append(paragraph.text)

        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        text_parts.append(cell.text)

        full_text = "\n".join(text_parts)
        return full_text.strip() or None

    except FileNotFoundError:
        raise FileNotFoundError(f"Word document not found: {file_path}")
    except Exception as e:
        raise Exception(f"Failed to extract text from Word document: {str(e)}")
