#!/usr/bin/env python3
"""
Occurrence Agent - Main Interface

Provides a simple interface for analyzing complaint occurrence using
pattern data and similar cases analysis.
"""

from typing import Dict, Any, Optional, List
from Agents.occurrence.state import ComplaintData, PatternData, SimilarCasesData, OccurrenceOutput
from Agents.occurrence.graph import occurrence_graph
from Agents.occurrence.logger import log_request, log_final_output, log_error
import json

class OccurrenceAgent:
    """
    Main interface for the Occurrence Agent.
    Handles both new structured format and legacy format.
    """
    
    def __init__(self):
        self.graph = occurrence_graph
    
    def analyze_with_pattern_and_similar_cases(
        self,
        complaint_id: str,
        description: str,
        source: str,
        date: str,
        product: str,
        pattern_data: Dict[str, Any],
        similar_cases_data: Dict[str, Any],
        additional_context: Optional[str] = None,
        metrics_data: Optional[str] = None
    ) -> OccurrenceOutput:
        """
        Analyze occurrence using pattern data and similar cases data.
        
        Args:
            complaint_id: Unique identifier for the complaint
            description: Description of the complaint/issue
            source: Source of the complaint (e.g., "Customer Report", "Quality Control")
            date: Date of the complaint (ISO format recommended)
            product: Product information
            pattern_data: Pattern analysis results (dict format)
            similar_cases_data: Similar cases analysis results (dict format)
            additional_context: Optional additional context
            metrics_data: Optional custom metrics JSON string
            
        Returns:
            OccurrenceOutput with weighted score, rating, and breakdown
        """
        try:
            # Parse structured data
            pattern_obj = PatternData(**pattern_data) if pattern_data else None
            similar_cases_obj = SimilarCasesData(**similar_cases_data) if similar_cases_data else None
            
            # Create input data
            input_data = ComplaintData(
                complaint_id=complaint_id,
                description=description,
                source=source,
                date=date,
                product=product,
                pattern_data=pattern_obj,
                similar_cases_data=similar_cases_obj,
                additional_context=additional_context,
                metrics_data=metrics_data
            )
            
            # Log request
            num_similar_cases = len(similar_cases_obj.topMatches) if similar_cases_obj else 0
            log_request(
                complaint_id=complaint_id,
                product=product,
                source=source,
                date=date,
                num_similar_cases=num_similar_cases,
                has_pattern_data=pattern_obj is not None
            )
            
            # Initialize state
            initial_state = {
                "input": input_data,
                "iteration": 0,
                "evidence_summary": None,
                "raw_scores": None,
                "final_output": None
            }
            
            # Run the graph
            result = self.graph.invoke(initial_state)
            final_output = result.get("final_output")
            
            if not final_output:
                raise ValueError("Agent failed to produce a final output.")
            
            # Log final output
            log_final_output(
                complaint_id=complaint_id,
                weighted_score=final_output.weighted_score,
                rating=final_output.rating
            )
            
            return final_output
            
        except Exception as e:
            log_error("analyze_with_pattern_and_similar_cases", str(e))
            raise
    
    def analyze_legacy_format(
        self,
        complaint_id: str,
        description: str,
        source: str,
        date: str,
        product: str,
        similar_cases: List[Dict[str, Any]],
        additional_context: Optional[str] = None,
        metrics_data: Optional[str] = None
    ) -> OccurrenceOutput:
        """
        Analyze occurrence using legacy similar cases format.
        
        Args:
            complaint_id: Unique identifier for the complaint
            description: Description of the complaint/issue
            source: Source of the complaint
            date: Date of the complaint
            product: Product information
            similar_cases: List of similar cases in legacy format
            additional_context: Optional additional context
            metrics_data: Optional custom metrics JSON string
            
        Returns:
            OccurrenceOutput with weighted score, rating, and breakdown
        """
        try:
            # Create input data with legacy format
            input_data = ComplaintData(
                complaint_id=complaint_id,
                description=description,
                source=source,
                date=date,
                product=product,
                similar_cases=similar_cases,
                additional_context=additional_context,
                metrics_data=metrics_data
            )
            
            # Log request
            log_request(
                complaint_id=complaint_id,
                product=product,
                source=source,
                date=date,
                num_similar_cases=len(similar_cases),
                has_pattern_data=False
            )
            
            # Initialize state
            initial_state = {
                "input": input_data,
                "iteration": 0,
                "evidence_summary": None,
                "raw_scores": None,
                "final_output": None
            }
            
            # Run the graph
            result = self.graph.invoke(initial_state)
            final_output = result.get("final_output")
            
            if not final_output:
                raise ValueError("Agent failed to produce a final output.")
            
            # Log final output
            log_final_output(
                complaint_id=complaint_id,
                weighted_score=final_output.weighted_score,
                rating=final_output.rating
            )
            
            return final_output
            
        except Exception as e:
            log_error("analyze_legacy_format", str(e))
            raise

# Convenience function for direct usage
def analyze_occurrence(
    complaint_id: str,
    description: str,
    source: str,
    date: str,
    product: str,
    pattern_data: Optional[Dict[str, Any]] = None,
    similar_cases_data: Optional[Dict[str, Any]] = None,
    similar_cases: Optional[List[Dict[str, Any]]] = None,
    additional_context: Optional[str] = None,
    metrics_data: Optional[str] = None
) -> OccurrenceOutput:
    """
    Convenience function to analyze occurrence with automatic format detection.
    
    Args:
        complaint_id: Unique identifier for the complaint
        description: Description of the complaint/issue
        source: Source of the complaint
        date: Date of the complaint
        product: Product information
        pattern_data: Optional pattern analysis results
        similar_cases_data: Optional similar cases analysis results
        similar_cases: Optional legacy similar cases list
        additional_context: Optional additional context
        metrics_data: Optional custom metrics JSON string
        
    Returns:
        OccurrenceOutput with weighted score, rating, and breakdown
    """
    agent = OccurrenceAgent()
    
    if pattern_data or similar_cases_data:
        # Use new format
        return agent.analyze_with_pattern_and_similar_cases(
            complaint_id=complaint_id,
            description=description,
            source=source,
            date=date,
            product=product,
            pattern_data=pattern_data or {},
            similar_cases_data=similar_cases_data or {},
            additional_context=additional_context,
            metrics_data=metrics_data
        )
    else:
        # Use legacy format
        return agent.analyze_legacy_format(
            complaint_id=complaint_id,
            description=description,
            source=source,
            date=date,
            product=product,
            similar_cases=similar_cases or [],
            additional_context=additional_context,
            metrics_data=metrics_data
        )