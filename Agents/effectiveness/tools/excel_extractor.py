"""
Excel Extractor Tool
Extracts text and structured data from .xlsx / .xls files for supporting evidence ingestion.
"""

from typing import Optional
import pandas as pd


def extract_text_from_excel(file_path: str) -> Optional[str]:
    """
    Extract all sheet content from an Excel file as plain text.

    Args:
        file_path: Path to the Excel file (.xlsx or .xls)

    Returns:
        Extracted text as string, or None if empty

    Raises:
        FileNotFoundError: If file doesn't exist
        Exception: If Excel parsing fails
    """
    try:
        excel_file = pd.ExcelFile(file_path)
        text_parts = []

        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            text_parts.append(f"=== Sheet: {sheet_name} ===")
            text_parts.append(df.to_string(index=False))
            text_parts.append("")

        full_text = "\n".join(text_parts)
        return full_text.strip() or None

    except FileNotFoundError:
        raise FileNotFoundError(f"Excel file not found: {file_path}")
    except Exception as e:
        raise Exception(f"Failed to extract text from Excel: {str(e)}")
