"""
PDF Extractor Tool
Extracts text from PDF files for supporting evidence ingestion.
"""

from typing import Optional
import PyPDF2


def extract_text_from_pdf(file_path: str) -> Optional[str]:
    """
    Extract raw text from a PDF file.

    Args:
        file_path: Path to the PDF file

    Returns:
        Extracted text as string, or None if empty

    Raises:
        FileNotFoundError: If file doesn't exist
        Exception: If PDF parsing fails
    """
    try:
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text_parts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)

        full_text = "\n".join(text_parts)
        return full_text.strip() or None

    except FileNotFoundError:
        raise FileNotFoundError(f"PDF file not found: {file_path}")
    except Exception as e:
        raise Exception(f"Failed to extract text from PDF: {str(e)}")
