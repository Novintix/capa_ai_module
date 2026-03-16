"""
Why Analysis Orchestrator Agent
Orchestrates Question Generation → Cause Generation → Zero Evidence pipeline
"""

import time
from typing import Dict, Any, List, Optional
from .schemas import (
    WhyAnalysisInput, 
    WhyAnalysisOutput,
    WhyIterationDetail,
    RootCauseDetail,
    CauseDetail
)
from .logger import log_error, log_iteration
from config.aws_bedrock_config import get_llm

# Import sub-agents
from Agents.cause_generation.schemas import QuestionInput
from Agents.cause_generation.agent import CauseGenerationAgent
from Agents.zero_evidence_agent.schemas import ZeroEvidenceInput, CauseInput
from Agents.zero_evidence_agent.agent import ZeroEvidenceAgent


class WhyAnalysisOrchestrator:
    """
    Enhanced Why Analysis Orchestrator that handles all scenarios:
    
    1. With FMEA: Iterates until no more causes found or max depth
    2. Without FMEA: Single iteration with LLM-generated causes
    3. FMEA extraction failures: Falls back to LLM generation
    4. No Redis dependency: Generates questions using LLM directly
    
    Features:
    - Complete error handling and fallbacks
    - Detailed iteration tracking for UI display
    - Memory management for question context
    - Clear input/output contracts
    """
    
    def __init__(self):
        """Initialize the orchestrator"""
        self.llm = get_llm()
        self.cause_agent = CauseGenerationAgent()
        self.zero_evidence_agent = ZeroEvidenceAgent()
    
    def analyze(self, input_data: WhyAnalysisInput) -> Dict[str, Any]:
        """
        Run complete Why Analysis with enhanced error handling
        
        Args:
            input_data: Enhanced input with all required fields
            
        Returns:
            Complete analysis result with detailed iteration tracking
        """
        start_time = time.time()
        
        try:
            # Initialize state
            state = {
                "complaint_id": input_data.complaint_id,
                "complaint": input_data.complaint,
                "evidence": input_data.evidence or "",
                "sop": input_data.sop or "",
                "fmea_document_path": input_data.fmea_document_path,
                "has_fmea": bool(input_data.fmea_document_path),
                "mode": "FMEA_ITERATIVE" if input_data.fmea_document_path else "NO_FMEA_SINGLE_SHOT",
                "current_depth": 0,
                "max_depth": input_data.max_depth or 5,
                "why_iterations": [],
                "question_context": [],  # Memory for question generation
                "final_root_cause": None,
                "confidence": "MEDIUM",
                "status": "running",
                "total_causes_analyzed": 0
            }
            
            # Main analysis loop
            while state["current_depth"] < state["max_depth"] and state["status"] == "running":
                iteration_result = self._process_iteration(state)
                
                if iteration_result["stop"]:
                    break
            
            # Calculate execution time
            execution_time = time.time() - start_time
            
            # Finalize result
            return self._build_final_result(state, execution_time)
            
        except Exception as e:
            log_error("analyze", str(e))
            execution_time = time.time() - start_time
            return {
                "complaint_id": input_data.complaint_id,
                "root_cause": None,
                "confidence": "LOW",
                "mode": "ERROR",
                "analysis_depth": 0,
                "why_iterations": [],
                "total_causes_analyzed": 0,
                "fmea_document_used": input_data.fmea_document_path,
                "execution_time_seconds": execution_time,
                "error": f"Orchestrator error: {str(e)}"
            }
    
    def _process_iteration(self, state: Dict[str, Any]) -> Dict[str, bool]:
        """
        Process a single Why iteration
        
        Returns:
            Dict with "stop" boolean indicating whether to continue
        """
        try:
            state["current_depth"] += 1
            
            # Step 1: Generate Why question
            why_question = self._generate_why_question(state)
            if not why_question:
                log_error("_process_iteration", f"Failed to generate question at depth {state['current_depth']}")
                return {"stop": True}
            
            # Step 2: Generate causes
            causes_result = self._generate_causes(state, why_question)
            
            # Convert causes to CauseDetail objects
            cause_details = []
            for cause in causes_result["causes"]:
                cause_details.append(CauseDetail(
                    cause_id=cause.get("cause_id", "UNKNOWN"),
                    cause_text=cause.get("cause_text", ""),
                    process_step=cause.get("process_step", ""),
                    failure_mode=cause.get("failure_mode"),
                    potential_effects=cause.get("potential_effects"),
                    severity=cause.get("severity"),
                    occurrence=cause.get("occurrence"),
                    detection=cause.get("detection"),
                    current_controls=cause.get("current_controls"),
                    source=cause.get("source", "FMEA")
                ))
            
            # Update total causes analyzed
            state["total_causes_analyzed"] += len(cause_details)
            
            # Step 3: Rank causes (if any found)
            selected_cause = None
            selected_cause_detail = None
            if cause_details:
                selected_cause = self._rank_causes(state, why_question, causes_result["causes"])
                if selected_cause:
                    # Find the original cause from causes_result to get all fields
                    original_cause = None
                    for cause in causes_result["causes"]:
                        if cause.get("cause_id") == selected_cause.get("cause_id"):
                            original_cause = cause
                            break
                    
                    # Use original cause if found, otherwise use selected_cause
                    cause_to_use = original_cause if original_cause else selected_cause
                    
                    selected_cause_detail = CauseDetail(
                        cause_id=cause_to_use.get("cause_id", "UNKNOWN"),
                        cause_text=cause_to_use.get("cause_text", ""),
                        process_step=cause_to_use.get("process_step", ""),
                        failure_mode=cause_to_use.get("failure_mode"),
                        potential_effects=cause_to_use.get("potential_effects"),
                        severity=cause_to_use.get("severity"),
                        occurrence=cause_to_use.get("occurrence"),
                        detection=cause_to_use.get("detection"),
                        current_controls=cause_to_use.get("current_controls"),
                        source=cause_to_use.get("source", "FMEA")
                    )
                    
                    # Update selected_cause with all fields for final root cause
                    selected_cause = cause_to_use
            
            # Step 4: Record iteration
            iteration = WhyIterationDetail(
                depth=state["current_depth"],
                question=why_question,
                reasoning=f"Generated question for depth {state['current_depth']}",
                causes_found=len(cause_details),
                causes=cause_details,
                selected_cause=selected_cause_detail,
                fmea_matches=causes_result.get("fmea_matches", 0),
                generation_method=causes_result.get("method", "unknown")
            )
            
            state["why_iterations"].append(iteration.dict())
            
            # Step 5: Update context for next iteration
            if selected_cause:
                state["question_context"].append({
                    "question": why_question,
                    "answer": selected_cause["cause_text"]
                })
                state["final_root_cause"] = selected_cause
            
            # Step 6: Decide whether to continue
            should_stop = self._should_stop_iteration(state, causes_result, selected_cause)
            
            log_iteration(
                state["current_depth"],
                why_question,
                len(cause_details),
                selected_cause["cause_text"] if selected_cause else None
            )
            
            return {"stop": should_stop}
            
        except Exception as e:
            log_error("_process_iteration", f"Iteration {state.get('current_depth', 0)} failed: {str(e)}")
            return {"stop": True}
    
    def _generate_why_question(self, state: Dict[str, Any]) -> Optional[str]:
        """
        Generate Why question using LLM with JSON format (compatible with AWS Bedrock config)
        """
        try:
            if state["current_depth"] == 1:
                # First question - based on complaint
                prompt = f"""You are a root cause analysis expert. Generate the first "Why?" question for this complaint.

COMPLAINT: {state['complaint']}

Generate a focused "Why?" question that probes the immediate cause of the problem.

Return ONLY valid JSON format:
{{
  "question": "Why did [specific issue occur]?"
}}

Example:
{{
  "question": "Why did the sealing temperature drop below specification?"
}}
"""
            else:
                # Subsequent questions - based on previous answers
                context_text = ""
                for i, ctx in enumerate(state["question_context"], 1):
                    context_text += f"Q{i}: {ctx['question']}\nA{i}: {ctx['answer']}\n\n"
                
                prompt = f"""You are a root cause analysis expert. Generate the next "Why?" question based on the previous analysis.

ORIGINAL COMPLAINT: {state['complaint']}

PREVIOUS WHY ANALYSIS:
{context_text}

Generate the next "Why?" question that digs deeper into the root cause. Focus on the last answer to go one level deeper.

Return ONLY valid JSON format:
{{
  "question": "Why did [specific deeper issue occur]?"
}}

Example:
{{
  "question": "Why was the temperature sensor not calibrated properly?"
}}
"""
            
            # Use the standard LLM interface
            response = self.llm.invoke(prompt)
            
            # Parse JSON response
            import json
            try:
                parsed = json.loads(response.content)
                question = parsed.get("question", "").strip()
            except json.JSONDecodeError as e:
                log_error("_generate_why_question", f"Failed to parse JSON response: {response.content}")
                return None
            
            # Validate we have a proper question
            if len(question.strip()) < 5:  # Minimum reasonable question length
                log_error("_generate_why_question", f"Generated question too short: '{question}'")
                return None
            
            # Ensure proper Why format
            if not question.lower().startswith("why"):
                question = f"Why {question.lower()}"
            if not question.endswith("?"):
                question += "?"
                
            return question
            
        except Exception as e:
            log_error("_generate_why_question", str(e))
            return None
    
    def _generate_causes(self, state: Dict[str, Any], question: str) -> Dict[str, Any]:
        """
        Generate causes using the Cause Generation Agent
        
        Special handling for depth 1 with FMEA:
        - If no FMEA matches found, fall back to LLM generation
        - If FMEA matches found but all filtered out, fall back to LLM generation
        """
        try:
            question_input = QuestionInput(
                question_id=f"{state['complaint_id']}_depth{state['current_depth']}",
                question=question,
                context=state["complaint"]
            )
            
            # Call cause generation agent
            result = self.cause_agent.process_question(
                question_input, 
                state.get("fmea_document_path")
            )
            
            # Filter out previously selected causes to avoid repetition
            causes = result.get("causes", [])
            
            # Special handling for depth 1: If FMEA returned no causes, try LLM generation
            if state["current_depth"] == 1 and not causes and state.get("fmea_document_path"):
                # FMEA was provided but no causes found - fall back to LLM
                result = self.cause_agent.process_question(
                    question_input, 
                    None  # Force LLM generation by not providing FMEA path
                )
                causes = result.get("causes", [])
            
            if state["question_context"]:
                # Get previously selected cause texts
                previous_causes = [ctx["answer"] for ctx in state["question_context"]]
                
                # Filter out causes that match previous selections
                filtered_causes = []
                for cause in causes:
                    cause_text = cause.get("cause_text", "")
                    # Check if this cause is substantially different from previous ones
                    is_duplicate = any(
                        cause_text.lower().strip() == prev.lower().strip() 
                        for prev in previous_causes
                    )
                    if not is_duplicate:
                        filtered_causes.append(cause)
                
                causes = filtered_causes
            
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
    
    def _rank_causes(self, state: Dict[str, Any], question: str, causes: List[Dict]) -> Optional[Dict]:
        """
        Rank causes using Zero Evidence Agent
        """
        try:
            if not causes:
                return None
            
            # Convert to CauseInput format
            cause_inputs = []
            for cause in causes:
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
                question_id=f"{state['complaint_id']}_depth{state['current_depth']}",
                question=question,
                causes=cause_inputs,
                total_causes=len(cause_inputs)
            )
            
            result = self.zero_evidence_agent.analyze(zero_input)
            return result.get("selected_root_cause")
            
        except Exception as e:
            log_error("_rank_causes", str(e))
            # Fallback to first cause
            return causes[0] if causes else None
    
    def _should_stop_iteration(self, state: Dict[str, Any], causes_result: Dict, selected_cause: Optional[Dict]) -> bool:
        """
        Determine if iteration should stop
        """
        # Stop if no causes found
        if not causes_result["causes"]:
            state["status"] = "no_causes_found"
            return True
        
        # Stop if no cause was selected
        if not selected_cause:
            state["status"] = "no_cause_selected"
            return True
        
        # Stop if max depth reached
        if state["current_depth"] >= state["max_depth"]:
            state["status"] = "max_depth_reached"
            return True
        
        # Stop if in NO_FMEA mode (single shot)
        if state["mode"] == "NO_FMEA_SINGLE_SHOT":
            state["status"] = "single_shot_complete"
            return True
        
        # Stop if same cause is being repeated (no deeper analysis possible)
        if len(state["question_context"]) >= 2:
            last_two_causes = [ctx["answer"] for ctx in state["question_context"][-2:]]
            if last_two_causes[0] == last_two_causes[1]:
                state["status"] = "cause_repetition_detected"
                return True
        
        # Stop if we've found the same cause 3 times in a row
        if len(state["question_context"]) >= 3:
            last_three_causes = [ctx["answer"] for ctx in state["question_context"][-3:]]
            if len(set(last_three_causes)) == 1:
                state["status"] = "cause_repetition_limit"
                return True
        
        # Continue if in FMEA mode and causes were found
        return False
    
    def _build_final_result(self, state: Dict[str, Any], execution_time: float) -> Dict[str, Any]:
        """
        Build the final result dictionary
        """
        # Determine final confidence
        confidence = "HIGH"
        if state["mode"] == "NO_FMEA_SINGLE_SHOT":
            confidence = "MEDIUM"
        elif not state["final_root_cause"]:
            confidence = "LOW"
        elif state["current_depth"] < 2:
            confidence = "MEDIUM"
        
        # Build root cause detail if available
        root_cause_detail = None
        if state["final_root_cause"]:
            rc = state["final_root_cause"]
            root_cause_detail = {
                "cause_id": rc.get("cause_id", "UNKNOWN"),
                "cause_text": rc.get("cause_text", ""),
                "process_step": rc.get("process_step", ""),
                "failure_mode": rc.get("failure_mode"),
                "potential_effects": rc.get("potential_effects"),
                "severity": rc.get("severity"),
                "occurrence": rc.get("occurrence"),
                "detection": rc.get("detection"),
                "current_controls": rc.get("current_controls"),
                "source": rc.get("source", "FMEA"),
                "reason": rc.get("reason", "Selected as most critical cause"),
                "confidence_score": rc.get("confidence_score", 0.8)
            }
        
        # Determine error message based on stopping reason
        error_msg = None
        if not state["final_root_cause"]:
            status = state.get("status", "unknown")
            if status == "no_causes_found":
                error_msg = "No causes could be identified for the given complaint"
            elif status == "cause_repetition_detected":
                error_msg = "Analysis stopped - same cause repeated, no deeper root cause available"
            elif status == "max_depth_reached":
                error_msg = "Analysis stopped - maximum depth reached"
            else:
                error_msg = "No root cause could be determined"
        
        return {
            "complaint_id": state["complaint_id"],
            "root_cause": root_cause_detail,
            "confidence": confidence,
            "mode": state["mode"],
            "analysis_depth": state["current_depth"],
            "why_iterations": state["why_iterations"],
            "total_causes_analyzed": state["total_causes_analyzed"],
            "fmea_document_used": state.get("fmea_document_path"),
            "execution_time_seconds": round(execution_time, 2),
            "stopping_reason": state.get("status", "completed"),
            "error": error_msg
        }