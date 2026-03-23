"""
RCA v2 Orchestrator Agent
Proper state machine implementation with controlled memory management
"""

import time
from typing import Dict, Any, List, Optional
from .schemas import WhyAnalysisInput, WhyAnalysisOutput
from .logger import log_error, log_iteration
from .state_machine import RCAStateMachine, RCAState, IterationMemory, StopReason
from config.aws_bedrock_config import get_llm

# Import sub-agents
from Agents.cause_generation.schemas import QuestionInput
from Agents.cause_generation.agent import CauseGenerationAgent
from Agents.zero_evidence_agent.schemas import ZeroEvidenceInput, CauseInput
from Agents.zero_evidence_agent.agent import ZeroEvidenceAgent


class RCAOrchestratorV2:
    """
    RCA v2 Orchestrator with proper state machine implementation
    
    Key improvements:
    - Central JSON state object (RCAStateMachine)
    - Controlled LLM context (no full history)
    - Orchestrator-only memory updates
    - Separate execution + control memory
    - Proper state machine transitions
    """
    
    def __init__(self):
        """Initialize the orchestrator"""
        self.llm = get_llm()
        self.cause_agent = CauseGenerationAgent()
        self.zero_evidence_agent = ZeroEvidenceAgent()
    
    def analyze(self, input_data: WhyAnalysisInput) -> Dict[str, Any]:
        """
        Run complete Why Analysis using state machine
        
        Args:
            input_data: Input with all required fields
            
        Returns:
            Complete analysis result with state machine tracking
        """
        try:
            # Input validation
            validation_error = self._validate_input(input_data)
            if validation_error:
                return self._create_validation_error_response(input_data, validation_error)
            
            # Initialize state machine
            state_machine = RCAStateMachine(
                complaint_id=input_data.complaint_id,
                complaint=input_data.complaint,
                evidence=input_data.evidence or "",
                sop=input_data.sop or "",
                fmea_document_path=input_data.fmea_document_path,
                max_depth=input_data.max_depth or 5
            )
            
            # State machine execution loop
            while state_machine.should_continue():
                success = self._execute_iteration(state_machine)
                if not success:
                    state_machine.transition_to(RCAState.ERROR, "Iteration execution failed")
                    break
            
            # Return final result from state machine
            return state_machine.get_final_result()
            
        except Exception as e:
            log_error("analyze", str(e))
            return self._create_error_response(input_data, str(e))
    
    def _execute_iteration(self, state_machine: RCAStateMachine) -> bool:
        """
        Execute a single iteration using state machine
        
        Args:
            state_machine: The central state machine
            
        Returns:
            True if successful, False if failed
        """
        try:
            # Start new iteration
            state_machine.start_new_iteration()
            
            # Step 1: Generate Why question (QUESTIONING state)
            question = self._generate_question(state_machine)
            if not question:
                log_error("_execute_iteration", f"Failed to generate question at depth {state_machine.control_memory.current_depth}")
                return False
            
            # Transition to cause finding
            state_machine.transition_to(RCAState.CAUSE_FINDING, "Question generated successfully")
            
            # Step 2: Generate causes (CAUSE_FINDING state)
            causes_result = self._generate_causes(state_machine, question)
            
            # Transition to cause ranking
            state_machine.transition_to(RCAState.CAUSE_RANKING, "Causes generated successfully")
            
            # Step 3: Rank causes (CAUSE_RANKING state)
            selected_cause = None
            if causes_result["causes"]:
                selected_cause = self._rank_causes(state_machine, question, causes_result["causes"])
            
            # Create iteration memory
            iteration = IterationMemory(
                depth=state_machine.control_memory.current_depth,
                question=question,
                causes_found=causes_result["causes"],
                selected_cause=selected_cause,
                fmea_matches=causes_result.get("fmea_matches", 0),
                generation_method=causes_result.get("method", "unknown")
            )
            
            # Complete iteration (updates memories and determines next state)
            state_machine.complete_iteration(iteration)
            
            # Log iteration
            log_iteration(
                iteration.depth,
                iteration.question,
                len(iteration.causes_found),
                selected_cause["cause_text"] if selected_cause else None
            )
            
            return True
            
        except Exception as e:
            log_error("_execute_iteration", f"Iteration failed: {str(e)}")
            return False
    
    def _generate_question(self, state_machine: RCAStateMachine) -> Optional[str]:
        """
        Generate Why question using controlled LLM context
        
        Args:
            state_machine: The central state machine
            
        Returns:
            Generated question or None if failed
        """
        try:
            # Get controlled context from state machine
            context = state_machine.get_llm_context_for_question()
            
            prompt = f"""You are a root cause analysis expert. Generate the next "Why?" question based on the provided context.

{context}

Generate a focused "Why?" question that probes deeper into the root cause.

Return ONLY valid JSON format:
{{
  "question": "Why did [specific issue occur]?"
}}

Example:
{{
  "question": "Why did the temperature sensor fail to detect the deviation?"
}}
"""
            
            # Call LLM with controlled context
            response = self.llm.invoke(prompt)
            
            # Parse JSON response
            import json
            try:
                parsed = json.loads(response.content)
                question = parsed.get("question", "").strip()
            except json.JSONDecodeError:
                log_error("_generate_question", f"Failed to parse JSON response: {response.content}")
                return None
            
            # Validate question
            if len(question.strip()) < 5:
                log_error("_generate_question", f"Generated question too short: '{question}'")
                return None
            
            # Ensure proper Why format
            if not question.lower().startswith("why"):
                question = f"Why {question.lower()}"
            if not question.endswith("?"):
                question += "?"
                
            return question
            
        except Exception as e:
            log_error("_generate_question", str(e))
            return None
    
    def _generate_causes(self, state_machine: RCAStateMachine, question: str) -> Dict[str, Any]:
        """
        Generate causes using the Cause Generation Agent
        
        Args:
            state_machine: The central state machine
            question: The why question
            
        Returns:
            Dictionary with causes and metadata
        """
        try:
            question_input = QuestionInput(
                question_id=f"{state_machine.complaint_id}_depth{state_machine.control_memory.current_depth}",
                question=question,
                context=state_machine.complaint
            )
            
            # Call cause generation agent
            result = self.cause_agent.process_question(
                question_input, 
                state_machine.fmea_document_path
            )
            
            causes = result.get("causes", [])
            
            # Special handling for depth 1: If FMEA returned no causes, try LLM generation
            if (state_machine.control_memory.current_depth == 1 and 
                not causes and 
                state_machine.fmea_document_path):
                
                # FMEA was provided but no causes found - fall back to LLM
                result = self.cause_agent.process_question(question_input, None)
                causes = result.get("causes", [])
            
            # Filter out previously selected causes to avoid repetition
            if state_machine.execution_memory.iterations:
                causes = self._filter_duplicate_causes(causes, state_machine.execution_memory.iterations)
            
            return {
                "causes": causes,
                "fmea_matches": result.get("matched_entries", 0),
                "method": "FMEA" if result.get("matched_entries", 0) > 0 else "LLM_Generated",
                "notes": result.get("notes", "")
            }
            
        except Exception as e:
            log_error("_generate_causes", str(e))
            return {
                "causes": [],
                "fmea_matches": 0,
                "method": "error",
                "notes": f"Cause generation failed: {str(e)}"
            }
    
    def _rank_causes(self, state_machine: RCAStateMachine, question: str, causes: List[Dict]) -> Optional[Dict]:
        """
        Rank causes using Zero Evidence Agent with controlled context
        
        Args:
            state_machine: The central state machine
            question: The why question
            causes: List of causes to rank
            
        Returns:
            Selected cause or None
        """
        try:
            if not causes:
                return None
            
            # Get controlled context from state machine
            context = state_machine.get_llm_context_for_ranking(question, causes)
            
            # Convert to CauseInput format
            cause_inputs = []
            for cause in context["causes"]:  # Use controlled context, not full causes
                cause_inputs.append(CauseInput(
                    cause_id=cause.get("cause_id", "UNKNOWN"),
                    cause_text=cause.get("cause_text", ""),
                    process_step=cause.get("process_step", ""),
                    failure_mode=cause.get("failure_mode", ""),
                    potential_effects=cause.get("potential_effects"),
                    severity=cause.get("severity"),
                    occurrence=cause.get("occurrence"),
                    detection=cause.get("detection"),
                    current_controls=cause.get("current_controls"),
                    source=cause.get("source", "FMEA")
                ))
            
            zero_input = ZeroEvidenceInput(
                question_id=f"{state_machine.complaint_id}_depth{state_machine.control_memory.current_depth}",
                question=question,
                causes=cause_inputs,
                total_causes=context["total_causes"]
            )
            
            result = self.zero_evidence_agent.analyze(zero_input)
            return result.get("selected_root_cause")
            
        except Exception as e:
            log_error("_rank_causes", str(e))
            # Fallback to first cause
            return causes[0] if causes else None
    
    def _filter_duplicate_causes(self, causes: List[Dict], previous_iterations: List[IterationMemory]) -> List[Dict]:
        """
        Filter out causes that match previous selections
        
        Args:
            causes: Current causes to filter
            previous_iterations: Previous iteration memories
            
        Returns:
            Filtered causes list
        """
        if not previous_iterations:
            return causes
        
        # Get previously selected cause texts
        previous_causes = []
        for iteration in previous_iterations:
            if iteration.selected_cause:
                previous_causes.append(iteration.selected_cause.get("cause_text", "").lower().strip())
        
        # Filter out duplicates
        filtered_causes = []
        for cause in causes:
            cause_text = cause.get("cause_text", "").lower().strip()
            if cause_text not in previous_causes:
                filtered_causes.append(cause)
        
        return filtered_causes
    
    def _validate_input(self, input_data: WhyAnalysisInput) -> Optional[str]:
        """
        Validate input to prevent hallucination on empty/invalid complaints
        
        Args:
            input_data: Input data to validate
            
        Returns:
            Error message if invalid, None if valid
        """
        # Check if complaint is empty or just whitespace
        complaint = input_data.complaint.strip() if input_data.complaint else ""
        
        if not complaint:
            return "Invalid input: Complaint description is required and cannot be empty. Please provide a detailed description of the problem or issue."
        
        # Check if complaint is too short to be meaningful
        if len(complaint) < 10:
            return f"Invalid input: Complaint description is too short ('{complaint}'). Please provide a detailed description of at least 10 characters explaining the problem."
        
        # Check if complaint contains only generic/placeholder text
        generic_phrases = [
            "test", "testing", "example", "sample", "placeholder", "lorem ipsum",
            "abc", "123", "xxx", "n/a", "na", "none", "null", "undefined"
        ]
        
        complaint_lower = complaint.lower()
        if any(phrase in complaint_lower for phrase in generic_phrases) and len(complaint) < 50:
            return f"Invalid input: Complaint appears to be placeholder text ('{complaint}'). Please provide a real problem description."
        
        # Check if complaint ID is meaningful
        complaint_id = input_data.complaint_id.strip() if input_data.complaint_id else ""
        if not complaint_id:
            return "Invalid input: Complaint ID is required and cannot be empty."
        
        # All validations passed
        return None
    
    def _create_validation_error_response(self, input_data: WhyAnalysisInput, error_msg: str) -> Dict[str, Any]:
        """Create validation error response"""
        return {
            "complaint_id": input_data.complaint_id,
            "root_cause": None,
            "confidence": "LOW",
            "mode": "VALIDATION_ERROR",
            "analysis_depth": 0,
            "why_iterations": [],
            "total_causes_analyzed": 0,
            "fmea_document_used": input_data.fmea_document_path,
            "execution_time_seconds": 0.0,
            "stopping_reason": "invalid_input",
            "error": error_msg
        }
    
    def _create_error_response(self, input_data: WhyAnalysisInput, error_msg: str) -> Dict[str, Any]:
        """Create general error response"""
        return {
            "complaint_id": input_data.complaint_id,
            "root_cause": None,
            "confidence": "LOW",
            "mode": "ERROR",
            "analysis_depth": 0,
            "why_iterations": [],
            "total_causes_analyzed": 0,
            "fmea_document_used": input_data.fmea_document_path,
            "execution_time_seconds": 0.0,
            "stopping_reason": "error_occurred",
            "error": f"Orchestrator error: {error_msg}"
        }