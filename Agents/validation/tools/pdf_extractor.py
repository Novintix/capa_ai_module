"""
PDF Extractor Tool
Extracts raw text from PDF documents.
"""

from typing import Optional
import PyPDF2


def extract_text_from_pdf(file_path: str) -> Optional[str]:
    """
    Extract raw text from PDF file.

    Args:
        file_path: Path to PDF file

    Returns:
        Extracted text as string, or None if extraction fails

    Raises:
        FileNotFoundError: If file doesn't exist
        Exception: If PDF parsing fails
    """

    try:
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)

            text_parts = []
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)

            full_text = "\n".join(text_parts)

            if not full_text.strip():
                return None

            return full_text

    except FileNotFoundError:
        raise FileNotFoundError(f"PDF file not found: {file_path}")
    except Exception as e:
        raise Exception(f"Failed to extract text from PDF: {str(e)}")
