"""
Excel FMEA Document Extractor
Extracts structured data from FMEA Excel files
"""

import pandas as pd
from typing import List, Dict, Any


def extract_fmea_from_excel(file_path: str) -> List[Dict[str, Any]]:
    """
    Extract FMEA data from Excel file
    
    Args:
        file_path: Path to Excel file
        
    Returns:
        List of dictionaries, each representing a row
    """
    try:
        # Read Excel file, skip first row if it contains headers
        df = pd.read_excel(file_path)
        
        # Clean up column names (strip whitespace, lowercase)
        df.columns = [str(col).strip().lower().replace(' ', '_') for col in df.columns]
        
        # Remove rows where key columns are header text (like "Severity", "Occurrence")
        # Check if first few rows contain header-like text
        if len(df) > 0:
            first_row_values = df.iloc[0].astype(str).str.lower()
            # If first row contains header keywords, skip it
            header_keywords = ['severity', 'occurrence', 'detection', 'process', 'failure', 'cause', 'effect']
            if any(keyword in ' '.join(first_row_values.values) for keyword in header_keywords):
                df = df.iloc[1:]  # Skip first data row (it's actually a header)
        
        # Convert to list of dictionaries
        fmea_data = df.to_dict('records')
        
        # Clean up data
        cleaned_data = []
        for row in fmea_data:
            cleaned_row = {}
            for key, value in row.items():
                # Convert NaN to None
                clean_value = None if pd.isna(value) else value
                cleaned_row[key] = clean_value
            
            # Skip rows that are all None or empty
            if any(v is not None and str(v).strip() for v in cleaned_row.values()):
                cleaned_data.append(cleaned_row)
        
        return cleaned_data
        
    except Exception as e:
        raise Exception(f"Failed to extract FMEA from Excel: {str(e)}")


def normalize_column_names(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalize column names to standard FMEA fields
    
    Maps various column name variations to standard names.
    Also handles unnamed columns by position.
    """
    
    normalized_data = []
    
    for row in data:
        normalized_row = {}
        
        # Get all keys
        keys = list(row.keys())
        
        # Map by column name or position
        for idx, (key, value) in enumerate(row.items()):
            key_lower = str(key).lower().strip()
            
            # Direct name mappings
            if 'process' in key_lower or 'risk_identification' in key_lower:
                normalized_row['process_step'] = value
            elif 'failure_mode' in key_lower or (key_lower.startswith('unnamed') and idx == 1):
                normalized_row['failure_mode'] = value
            elif 'effect' in key_lower or 'risk_analysis' in key_lower or (key_lower.startswith('unnamed') and idx == 2):
                normalized_row['effects'] = value
            elif 'severity' in key_lower or (key_lower.startswith('unnamed') and idx == 3):
                normalized_row['severity'] = value
            elif 'cause' in key_lower or (key_lower.startswith('unnamed') and idx == 4):
                normalized_row['causes'] = value
            elif 'occurrence' in key_lower or (key_lower.startswith('unnamed') and idx == 5):
                normalized_row['occurrence'] = value
            elif 'control' in key_lower or (key_lower.startswith('unnamed') and idx == 6):
                normalized_row['current_controls'] = value
            elif 'detection' in key_lower or (key_lower.startswith('unnamed') and idx == 7):
                normalized_row['detection'] = value
            else:
                # Keep original key for unmapped columns
                normalized_row[key] = value
        
        normalized_data.append(normalized_row)
    
    return normalized_data
