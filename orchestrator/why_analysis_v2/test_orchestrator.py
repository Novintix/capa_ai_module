"""Integration-style tests for why_analysis_v2 orchestration flow.

These tests mock downstream agents so we can verify routing and state handling
for each branch deterministically.
"""

from __future__ import annotations

from typing import Any, Dict, List

from orchestrator.why_analysis_v2 import orchestrator as orch
from orchestrator.why_analysis_v2.agent import WhyAnalysisV2Orchestrator
from orchestrator.why_analysis_v2.schemas import WhyAnalysisV2Input


def _cause(cause_id: str, cause_text: str, severity: int = 7) -> Dict[str, Any]:
    return {
        "cause_id": cause_id,
        "cause_text": cause_text,
        "process_step": "Verification",
        "failure_mode": "Procedure not followed",
        "potential_effects": "Risk of contamination",
        "severity": severity,
        "occurrence": 4,
        "detection": 3,
        "current_controls": "Supervisor sign-off",
        "source": "Generated",
    }


class StubQuestionAgent:
    def __init__(self, questions: List[str]):
        self._questions = questions
        self.start_calls = 0
        self.continue_calls = 0

    def start(self, input_data):
        self.start_calls += 1
        return {
            "complaint_id": input_data.complaint_id,
            "why_question": self._questions[0],
            "reasoning": "Start why",
            "why_depth": 1,
            "error": None,
        }

    def continue_chain(self, input_data):
        self.continue_calls += 1
        idx = min(self.continue_calls, len(self._questions) - 1)
        return {
            "complaint_id": input_data.complaint_id,
            "why_question": self._questions[idx],
            "reasoning": "Continue why",
            "why_depth": idx + 1,
            "error": None,
        }


class StubCauseGenerationAgent:
    def __init__(self, by_question: Dict[str, List[Dict[str, Any]]]):
        self.by_question = by_question

    def process_question(self, question_input, fmea_document_path=None):
        causes = self.by_question.get(question_input.question, [])
        return {
            "question_id": question_input.question_id,
            "question": question_input.question,
            "causes": causes,
            "total_causes": len(causes),
            "fmea_document_used": fmea_document_path or "Not Available",
            "matched_entries": 0,
            "confidence": 0.8,
            "notes": "stub",
        }


class StubValidationAgent:
    def __init__(self, results: List[Dict[str, Any]]):
        self._results = list(results)
        self.calls = 0

    def validate_causes(self, validation_input):
        self.calls += 1
        if self._results:
            return self._results.pop(0)
        return {
            "complaint_id": validation_input.complaint_id,
            "complaint_description": validation_input.complaint_description,
            "total_input_causes": len(validation_input.generated_causes),
            "total_validated_causes": 0,
            "validated_causes": [],
            "cause_validation_results": [],
            "overall_confidence": 0.0,
            "notes": "stub default",
        }


class StubRankingAgent:
    def rank_causes(self, causes, config=None):
        ranked = []
        for idx, cause in enumerate(causes, start=1):
            ranked.append(
                {
                    "rank": idx,
                    "cause_id": cause["cause_id"],
                    "cause_text": cause["cause_text"],
                    "rcps_score": 0.95 - (idx * 0.05),
                    "rpn": cause["severity"] * cause["occurrence"] * cause["detection"],
                    "rpn_score": 0.9,
                    "evidence_strength": 1.0,
                    "mechanism_fit": 0.9,
                    "causal_proximity": 1.0,
                    "risk_level": "High",
                    "justification": "stub",
                    "confidence": 0.9,
                }
            )

        return {
            "ranked_causes": ranked,
            "selected_root_cause": ranked[0]["cause_id"],
            "total_causes": len(ranked),
            "domain": (config or {}).get("domain", "generic"),
            "config_used": {
                "domain": (config or {}).get("domain", "generic"),
                "weights": {
                    "rpn_weight": 0.35,
                    "evidence_weight": 0.30,
                    "mechanism_weight": 0.20,
                    "proximity_weight": 0.15,
                },
                "max_causes": 20,
                "evidence_context": "investigation",
                "mechanism_context": "technical analysis",
                "proximity_context": "causal analysis",
            },
            "message": "stub",
            "metadata": None,
        }


class StubZeroEvidenceAgent:
    def analyze(self, input_data):
        selected = input_data.causes[-1]
        return {
            "mode": "ZERO_EVIDENCE_MODE",
            "selected_root_cause": {
                "cause_id": selected.cause_id,
                "cause_text": selected.cause_text,
                "process_step": selected.process_step,
                "reason": "stub zero evidence pick",
            },
            "confidence": "MEDIUM",
        }


class StubLoopControlAgent:
    def __init__(self, decisions: List[str]):
        self._decisions = list(decisions)
        self.calls = 0

    def evaluate(self, payload):
        self.calls += 1
        decision = self._decisions.pop(0)
        return {
            "decision": decision,
            "reasoning": f"stub {decision}",
            "chain_health": {
                "circular": False,
                "specificity_trend": "increasing",
                "confidence_trend": "increasing",
            },
            "root_cause_score": {
                "actionability": 3,
                "system_depth": 3,
                "recurrence_prevention": 3,
                "total": 9,
            },
            "next_step": None if decision != "LOOP" else {
                "target": payload.current_top_cause,
                "probe_angle": "process",
                "avoid": "avoid repetition",
                "evidence_hint": "collect concrete evidence",
            },
        }


def _base_input() -> WhyAnalysisV2Input:
    return WhyAnalysisV2Input(
        complaint_id="CAPA-ORCH-001",
        complaint="Contamination spike after maintenance restart.",
        evidence="Operator crossed sterile boundary; no line clearance record.",
        sop="SOP requires Clear-Clean-Check after intervention.",
        max_loops=5,
    )


def _assert_iteration_keys(iteration: Dict[str, Any]):
    required_keys = {
        "question_agent_input",
        "question_agent_output",
        "cause_generation_agent_input",
        "cause_generation_agent_output",
        "validation_agent_input",
        "validation_agent_output",
        "ranking_agent_input",
        "ranking_agent_output",
        "zero_evidence_agent_input",
        "zero_evidence_agent_output",
        "loop_control_agent_input",
        "loop_control_agent_output",
    }
    missing = required_keys - set(iteration.keys())
    assert not missing, f"Missing iteration trace keys: {missing}"


def test_flow_single_validated_goes_to_loop_control(monkeypatch):
    q1 = "Why was line clearance skipped?"
    c1 = _cause("C001", "SOP exists but enforcement ownership was unclear across shifts.", severity=8)

    question_agent = StubQuestionAgent([q1])
    cause_agent = StubCauseGenerationAgent({q1: [c1]})
    validation_agent = StubValidationAgent(
        [
            {
                "complaint_id": "CAPA-ORCH-001",
                "complaint_description": "Contamination spike after maintenance restart.",
                "total_input_causes": 1,
                "total_validated_causes": 1,
                "validated_causes": [{**c1, "evidence_match_status": "matched", "supporting_evidence_references": ["inv.txt"], "confidence": 0.85, "rationale": "strong"}],
                "cause_validation_results": [{**c1, "evidence_match_status": "matched", "supporting_evidence_references": ["inv.txt"], "confidence": 0.85, "rationale": "strong"}],
                "overall_confidence": 0.85,
                "notes": "ok",
            }
        ]
    )
    ranking_agent = StubRankingAgent()
    zero_agent = StubZeroEvidenceAgent()
    loop_agent = StubLoopControlAgent(["STOP_ROOT_FOUND"])

    monkeypatch.setattr(orch, "_get_question_agent", lambda: question_agent)
    monkeypatch.setattr(orch, "_get_cause_agent", lambda: cause_agent)
    monkeypatch.setattr(orch, "_get_validation_agent", lambda: validation_agent)
    monkeypatch.setattr(orch, "_get_ranking_agent", lambda: ranking_agent)
    monkeypatch.setattr(orch, "_get_zero_evidence_agent", lambda: zero_agent)
    monkeypatch.setattr(orch, "_get_loop_control_agent", lambda: loop_agent)

    output = WhyAnalysisV2Orchestrator().analyze(_base_input())

    assert output["status"] == "completed"
    assert output["analysis_depth"] == 1
    assert output["root_cause"]["cause_id"] == "C001"
    assert len(output["iteration_outputs"]) == 1
    _assert_iteration_keys(output["iteration_outputs"][0])
    assert output["iteration_outputs"][0]["ranking_agent_output"] == {}
    assert output["iteration_outputs"][0]["loop_control_agent_output"]["decision"] == "STOP_ROOT_FOUND"


def test_flow_multi_validated_goes_ranking_then_loop_then_continue(monkeypatch):
    q1 = "Why was line clearance skipped?"
    q2 = "Why was accountability weak after SOP update?"
    c1 = _cause("C001", "Tooling gap: system lacks enforcement gate for post-maintenance verification.", severity=9)
    c2 = _cause("C002", "Training gap on revised SOP after intervention.", severity=8)
    c3 = _cause("C003", "Organizational escalation ownership unclear between QA and Production.", severity=8)

    question_agent = StubQuestionAgent([q1, q2])
    cause_agent = StubCauseGenerationAgent({q1: [c1, c2], q2: [c3]})
    validation_agent = StubValidationAgent(
        [
            {
                "complaint_id": "CAPA-ORCH-001",
                "complaint_description": "Contamination spike after maintenance restart.",
                "total_input_causes": 2,
                "total_validated_causes": 2,
                "validated_causes": [
                    {**c1, "evidence_match_status": "matched", "supporting_evidence_references": ["inv.txt"], "confidence": 0.82, "rationale": "strong"},
                    {**c2, "evidence_match_status": "partially_matched", "supporting_evidence_references": ["sop.txt"], "confidence": 0.7, "rationale": "partial"},
                ],
                "cause_validation_results": [],
                "overall_confidence": 0.76,
                "notes": "ok",
            },
            {
                "complaint_id": "CAPA-ORCH-001",
                "complaint_description": "Contamination spike after maintenance restart.",
                "total_input_causes": 1,
                "total_validated_causes": 1,
                "validated_causes": [
                    {**c3, "evidence_match_status": "matched", "supporting_evidence_references": ["handover.txt"], "confidence": 0.86, "rationale": "strong"}
                ],
                "cause_validation_results": [],
                "overall_confidence": 0.86,
                "notes": "ok",
            },
        ]
    )
    ranking_agent = StubRankingAgent()
    zero_agent = StubZeroEvidenceAgent()
    loop_agent = StubLoopControlAgent(["LOOP", "STOP_ROOT_FOUND"])

    monkeypatch.setattr(orch, "_get_question_agent", lambda: question_agent)
    monkeypatch.setattr(orch, "_get_cause_agent", lambda: cause_agent)
    monkeypatch.setattr(orch, "_get_validation_agent", lambda: validation_agent)
    monkeypatch.setattr(orch, "_get_ranking_agent", lambda: ranking_agent)
    monkeypatch.setattr(orch, "_get_zero_evidence_agent", lambda: zero_agent)
    monkeypatch.setattr(orch, "_get_loop_control_agent", lambda: loop_agent)

    output = WhyAnalysisV2Orchestrator().analyze(_base_input())

    assert output["status"] == "completed"
    assert output["analysis_depth"] == 2
    assert len(output["iteration_outputs"]) == 2
    _assert_iteration_keys(output["iteration_outputs"][0])
    _assert_iteration_keys(output["iteration_outputs"][1])

    assert output["iteration_outputs"][0]["branch"] == "ranking_after_multi_validation"
    assert output["iteration_outputs"][0]["ranking_agent_output"]["selected_root_cause"] in {"C001", "C002"}
    assert output["iteration_outputs"][0]["loop_control_agent_output"]["decision"] == "LOOP"

    assert output["iteration_outputs"][1]["branch"] == "single_validated_no_ranking"
    assert output["iteration_outputs"][1]["loop_control_agent_output"]["decision"] == "STOP_ROOT_FOUND"


def test_flow_zero_validated_goes_to_zero_evidence(monkeypatch):
    q1 = "Why was line clearance skipped?"
    c1 = _cause("C001", "Training gap on revised SOP after intervention.", severity=8)
    c2 = _cause("C002", "Responsibility for line clearance not clearly assigned.", severity=8)

    question_agent = StubQuestionAgent([q1])
    cause_agent = StubCauseGenerationAgent({q1: [c1, c2]})
    validation_agent = StubValidationAgent(
        [
            {
                "complaint_id": "CAPA-ORCH-001",
                "complaint_description": "Contamination spike after maintenance restart.",
                "total_input_causes": 2,
                "total_validated_causes": 0,
                "validated_causes": [],
                "cause_validation_results": [],
                "overall_confidence": 0.0,
                "notes": "none",
            }
        ]
    )
    ranking_agent = StubRankingAgent()
    zero_agent = StubZeroEvidenceAgent()
    loop_agent = StubLoopControlAgent(["STOP_ROOT_FOUND"])

    monkeypatch.setattr(orch, "_get_question_agent", lambda: question_agent)
    monkeypatch.setattr(orch, "_get_cause_agent", lambda: cause_agent)
    monkeypatch.setattr(orch, "_get_validation_agent", lambda: validation_agent)
    monkeypatch.setattr(orch, "_get_ranking_agent", lambda: ranking_agent)
    monkeypatch.setattr(orch, "_get_zero_evidence_agent", lambda: zero_agent)
    monkeypatch.setattr(orch, "_get_loop_control_agent", lambda: loop_agent)

    output = WhyAnalysisV2Orchestrator().analyze(_base_input())

    assert output["status"] == "ai_flagged"
    assert output["stopping_reason"] == "no_validated_cause_zero_evidence"
    assert len(output["iteration_outputs"]) == 1
    _assert_iteration_keys(output["iteration_outputs"][0])
    assert output["iteration_outputs"][0]["zero_evidence_agent_output"]["mode"] == "ZERO_EVIDENCE_MODE"
    assert output["iteration_outputs"][0]["loop_control_agent_output"] == {}
