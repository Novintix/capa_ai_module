"""
TXT File Text Extraction Tool
"""


def extract_text_from_txt(file_path: str) -> str:
    """Extract UTF-8 text from a plain text file."""
    with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
        return file.read()
