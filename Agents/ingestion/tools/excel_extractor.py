"""
Excel Document Extractor
Extracts data from Excel (.xlsx, .xls) files
"""

import pandas as pd
from typing import Dict, Any, List


def extract_text_from_excel(file_path: str) -> str:
    """
    Extract text content from Excel file (all sheets)
    
    Args:
        file_path: Path to Excel file
        
    Returns:
        Extracted text as string
    """
    try:
        # Read all sheets
        excel_file = pd.ExcelFile(file_path)
        all_text = []
        
        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            
            # Convert dataframe to text
            sheet_text = f"Sheet: {sheet_name}\n"
            sheet_text += df.to_string(index=False)
            all_text.append(sheet_text)
        
        return "\n\n".join(all_text)
        
    except Exception as e:
        raise Exception(f"Failed to extract text from Excel: {str(e)}")


def extract_structured_from_excel(file_path: str) -> Dict[str, Any]:
    """
    Extract structured data from Excel file
    
    Args:
        file_path: Path to Excel file
        
    Returns:
        Dictionary with structured data per sheet
    """
    try:
        excel_file = pd.ExcelFile(file_path)
        structured_data = {}
        
        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            
            # Convert to list of dictionaries
            records = df.to_dict('records')
            
            # Clean NaN values
            cleaned_records = []
            for record in records:
                cleaned_record = {}
                for key, value in record.items():
                    if pd.notna(value):
                        cleaned_record[key] = value
                    else:
                        cleaned_record[key] = None
                cleaned_records.append(cleaned_record)
            
            structured_data[sheet_name] = {
                "columns": list(df.columns),
                "num_rows": len(df),
                "num_columns": len(df.columns),
                "data": cleaned_records
            }
        
        return {
            "sheets": structured_data,
            "num_sheets": len(excel_file.sheet_names),
            "sheet_names": excel_file.sheet_names
        }
        
    except Exception as e:
        raise Exception(f"Failed to extract structured data from Excel: {str(e)}")
