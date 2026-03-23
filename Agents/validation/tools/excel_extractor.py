"""
Excel Extractor Tool
Extracts raw text and structured data from Excel files.
"""

from typing import Optional
import pandas as pd


def extract_text_from_excel(file_path: str) -> Optional[str]:
    """
    Extract raw text from Excel file.
    Converts all sheets to text format.

    Args:
        file_path: Path to Excel file (.xlsx, .xls)

    Returns:
        Extracted text as string, or None if extraction fails

    Raises:
        FileNotFoundError: If file doesn't exist
        Exception: If Excel parsing fails
    """

    try:
        # Read all sheets
        excel_file = pd.ExcelFile(file_path)

        text_parts = []

        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet_name)

            # Add sheet name as header
            text_parts.append(f"=== Sheet: {sheet_name} ===")

            # Convert dataframe to text
            text_parts.append(df.to_string(index=False))
            text_parts.append("")

        full_text = "\n".join(text_parts)

        if not full_text.strip():
            return None

        return full_text

    except FileNotFoundError:
        raise FileNotFoundError(f"Excel file not found: {file_path}")
    except Exception as e:
        raise Exception(f"Failed to extract text from Excel: {str(e)}")


def extract_structured_from_excel(file_path: str, sheet_name: Optional[str] = None) -> Optional[pd.DataFrame]:
    """
    Extract structured data from Excel file as DataFrame.

    Args:
        file_path: Path to Excel file
        sheet_name: Specific sheet to extract (None = first sheet)

    Returns:
        DataFrame with extracted data, or None if extraction fails
    """

    try:
        if sheet_name:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
        else:
            df = pd.read_excel(file_path)

        return df

    except Exception as e:
        raise Exception(f"Failed to extract structured data from Excel: {str(e)}")
