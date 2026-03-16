"""
FMEA Extractor Tool
Extracts cause data from FMEA CSV files for ranking
"""

import csv
from typing import List, Dict, Any
import os


class FMEAExtractor:
    """Extract and parse FMEA data from CSV files."""
    
    def __init__(self, csv_path: str = None):
        """
        Initialize FMEA extractor.
        
        Args:
            csv_path: Path to FMEA CSV file
        """
        if csv_path is None:
            csv_path = os.path.join(
                os.path.dirname(__file__),
                "FMEA SAMPLE TEMPLATE.csv"
            )
        self.csv_path = csv_path
    
    def extract_causes(self, filter_process: str = None) -> List[Dict[str, Any]]:
        """
        Extract causes from FMEA CSV.
        
        Args:
            filter_process: Optional process step to filter by
            
        Returns:
            List of cause dictionaries with FMEA data
        """
        try:
            # Try different encodings
            for encoding in ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']:
                try:
                    with open(self.csv_path, 'r', encoding=encoding) as f:
                        reader = csv.DictReader(f)
                        break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError("Could not decode CSV file with any common encoding")
        except Exception as e:
            raise ValueError(f"Failed to open CSV file: {e}")
        
        causes = []
        try:
            # Try different encodings
            for encoding in ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']:
                try:
                    with open(self.csv_path, 'r', encoding=encoding) as f:
                        # Read all lines first to handle complex headers
                        lines = f.readlines()
                        
                        # Find the actual header row (should contain "Process", "Potential Failure Mode", etc.)
                        header_row_idx = None
                        for i, line in enumerate(lines):
                            if 'Process' in line and 'Potential Failure Mode' in line and 'Severity' in line:
                                header_row_idx = i
                                break
                        
                        if header_row_idx is None:
                            # Fallback: assume row 1 is headers
                            header_row_idx = 1
                        
                        # Create reader starting from the correct header row
                        f.seek(0)
                        for _ in range(header_row_idx):
                            next(f)
                        
                        reader = csv.DictReader(f)
                        
                        for idx, row in enumerate(reader, start=1):
                            # Skip description rows
                            process = row.get('Process', '').strip()
                            if process.startswith('(What is') or not process:
                                continue
                            
                            failure_mode = row.get('Potential Failure Mode', '').strip()
                            potential_effects = row.get('Potential Effects', '').strip()
                            cause_text = row.get('Potential Causes', '').strip()
                            
                            # Skip empty rows
                            if not cause_text or cause_text.startswith('What causes'):
                                continue
                            
                            # Apply filter if specified
                            if filter_process and filter_process.lower() not in process.lower():
                                continue
                            
                            # Parse numeric fields with multiple possible column names
                            severity_cols = ['Severity']
                            occurrence_cols = ['Occurrence'] 
                            detection_cols = ['Detection Level', 'Detection']
                            
                            severity = 5
                            occurrence = 3
                            detection = 5
                            
                            for col in severity_cols:
                                if col in row and row[col]:
                                    try:
                                        severity = int(float(row[col]))
                                        break
                                    except (ValueError, TypeError):
                                        pass
                            
                            for col in occurrence_cols:
                                if col in row and row[col]:
                                    try:
                                        occurrence = int(float(row[col]))
                                        break
                                    except (ValueError, TypeError):
                                        pass
                            
                            for col in detection_cols:
                                if col in row and row[col]:
                                    try:
                                        detection = int(float(row[col]))
                                        break
                                    except (ValueError, TypeError):
                                        pass
                            
                            cause = {
                                "cause_id": f"C{len(causes)+1:03d}",
                                "cause_text": cause_text,
                                "process_step": process,
                                "failure_mode": failure_mode,
                                "potential_effects": potential_effects,
                                "severity": severity,
                                "occurrence": occurrence,
                                "detection": detection
                            }
                            
                            causes.append(cause)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError("Could not decode CSV file with any common encoding")
        except Exception as e:
            raise ValueError(f"Failed to process CSV file: {e}")
        
        return causes
    
    def extract_by_failure_mode(self, failure_mode_keyword: str) -> List[Dict[str, Any]]:
        """
        Extract causes matching a specific failure mode.
        
        Args:
            failure_mode_keyword: Keyword to search in failure mode
            
        Returns:
            List of matching causes
        """
        all_causes = self.extract_causes()
        
        matching_causes = [
            c for c in all_causes
            if failure_mode_keyword.lower() in c['failure_mode'].lower()
        ]
        
        return matching_causes


def get_fmea_extractor(csv_path: str = None) -> FMEAExtractor:
    """
    Get FMEA extractor instance.
    
    Args:
        csv_path: Optional path to FMEA CSV file
        
    Returns:
        FMEAExtractor instance
    """
    return FMEAExtractor(csv_path)
