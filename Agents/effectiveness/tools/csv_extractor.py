"""
CSV Extractor Tool
Extracts text from CSV files for supporting evidence ingestion.
"""

from typing import Optional
import pandas as pd


def extract_text_from_csv(file_path: str) -> Optional[str]:
    """
    Extract content from a CSV file as plain text.

    Args:
        file_path: Path to the CSV file

    Returns:
        Extracted text as string, or None if empty

    Raises:
        FileNotFoundError: If file doesn't exist
        Exception: If CSV parsing fails
    """
    try:
        df = pd.read_csv(file_path, sep=None, engine="python", on_bad_lines="skip")
        text = df.to_string(index=False)
        return text.strip() or None

    except FileNotFoundError:
        raise FileNotFoundError(f"CSV file not found: {file_path}")
    except Exception as e:
        raise Exception(f"Failed to extract text from CSV: {str(e)}")
