"""Tests for Loop Control agent decision policy and stability."""

import pytest

from Agents.loop_control import nodes, utils
from Agents.loop_control.agent import LoopControlAgent
from Agents.loop_control.state import ChainHealth, LoopControlInput, LoopSignals, RootCauseScore


def _build_input(
	cause_text: str,
	loop: int = 3,
	max_loops: int = 6,
	confidence: float = 0.7,
) -> LoopControlInput:
	return LoopControlInput(
		incident_description="Product contamination trend increased after maintenance intervention.",
		current_loop_count=loop,
		max_loops=max_loops,
		current_top_cause=cause_text,
		current_cause_confidence=confidence,
		full_why_chain=[
			{
				"loop": 1,
				"question": "Why was contamination observed?",
				"cause": "Cleaning verification was inconsistent.",
				"confidence": 0.61,
			},
			{
				"loop": 2,
				"question": "Why was verification inconsistent?",
				"cause": "SOP adherence checks were not consistently enforced.",
				"confidence": 0.68,
			},
			{
				"loop": max(loop, 1),
				"question": "Why were adherence checks not enforced?",
				"cause": cause_text,
				"confidence": confidence,
			},
		],
	)


@pytest.mark.parametrize(
	"cause_text",
	[
		"System design flaw in change-control workflow allows SOP updates without retraining gate.",
		"SOP exists but was not followed due to lack of enforcement ownership.",
		"Tooling gap: no automated interlock to block release when verification is incomplete.",
		"Organizational issue: escalation ownership is unclear across production and QA.",
		"Training gap: operators were not requalified after SOP revision.",
		"Resource constraint: chronic understaffing removed time for mandatory line clearance.",
	],
)
def test_systemic_categories_calibrate_to_depth_three(cause_text: str):
	assert utils._calibrate_system_depth(cause_text, 2) == 3


def test_decide_returns_stop_degraded_for_degraded_chain():
	agent_input = _build_input("Repeated non-specific cause wording", loop=4)
	chain_health = ChainHealth(circular=True, specificity_trend="decreasing", confidence_trend="stable")
	score = RootCauseScore(actionability=2, system_depth=2, recurrence_prevention=2, total=6)
	signals = LoopSignals(
		fmea_gap=False,
		degraded=True,
		boundary_crossed=False,
		team_cannot_fix=False,
		alignment="weak",
		assessed_confidence=0.6,
	)

	decision, reasoning, next_step = utils.decide(agent_input, chain_health, score, signals)

	assert decision == "STOP_DEGRADED"
	assert "degraded" in reasoning.lower()
	assert next_step is None


def test_decide_uses_assessed_confidence_for_root_stop():
	agent_input = _build_input(
		"SOP exists but was not followed due to lack of enforcement ownership.",
		loop=3,
		confidence=0.55,
	)
	chain_health = ChainHealth(circular=False, specificity_trend="increasing", confidence_trend="stable")
	score = RootCauseScore(actionability=2, system_depth=3, recurrence_prevention=2, total=7)
	signals = LoopSignals(
		fmea_gap=False,
		degraded=False,
		boundary_crossed=False,
		team_cannot_fix=False,
		alignment="strong",
		assessed_confidence=0.82,
	)

	decision, _, next_step = utils.decide(agent_input, chain_health, score, signals)

	assert decision == "STOP_ROOT_FOUND"
	assert next_step is None


def test_decide_stops_degraded_when_max_loops_reached_without_root():
	agent_input = _build_input("Local condition explanation only", loop=6, max_loops=6)
	chain_health = ChainHealth(circular=False, specificity_trend="stable", confidence_trend="stable")
	score = RootCauseScore(actionability=2, system_depth=2, recurrence_prevention=2, total=6)
	signals = LoopSignals(
		fmea_gap=False,
		degraded=False,
		boundary_crossed=False,
		team_cannot_fix=False,
		alignment="weak",
		assessed_confidence=0.5,
	)

	decision, reasoning, next_step = utils.decide(agent_input, chain_health, score, signals)

	assert decision == "STOP_DEGRADED"
	assert "maximum" in reasoning.lower()
	assert next_step is None


def test_score_root_cause_uses_deterministic_fallback_on_llm_failure(monkeypatch):
	def _raise_llm_failure(_payload):
		raise RuntimeError("llm unavailable")

	monkeypatch.setattr(utils, "_assess_root_cause", _raise_llm_failure)

	agent_input = _build_input(
		"SOP exists but was not followed due to lack of enforcement ownership.",
		loop=3,
		confidence=0.73,
	)
	chain_health = ChainHealth(circular=False, specificity_trend="stable", confidence_trend="stable")

	score, signals = utils.score_root_cause(agent_input, chain_health)

	assert signals.llm_fallback is True
	assert "llm unavailable" in (signals.llm_fallback_reason or "")
	assert score.system_depth == 3
	assert 0.0 <= signals.assessed_confidence <= 1.0


def test_agent_evaluate_end_to_end_stop_root_found(monkeypatch):
	def _mock_chain_health(_payload):
		return ChainHealth(circular=False, specificity_trend="increasing", confidence_trend="stable")

	def _mock_score(_payload, _chain_health):
		return (
			RootCauseScore(actionability=3, system_depth=3, recurrence_prevention=3, total=9),
			LoopSignals(
				fmea_gap=False,
				degraded=False,
				boundary_crossed=False,
				team_cannot_fix=False,
				alignment="strong",
				assessed_confidence=0.92,
			),
		)

	monkeypatch.setattr(nodes, "evaluate_chain_health", _mock_chain_health)
	monkeypatch.setattr(nodes, "score_root_cause", _mock_score)

	agent = LoopControlAgent()
	output = agent.evaluate(
		_build_input(
			"Tooling gap: no automated interlock to block release when verification is incomplete.",
			loop=4,
			confidence=0.7,
		)
	)

	assert output["decision"] == "STOP_ROOT_FOUND"
	assert output["next_step"] is None


def test_agent_evaluate_end_to_end_stop_degraded(monkeypatch):
	def _mock_chain_health(_payload):
		return ChainHealth(circular=True, specificity_trend="decreasing", confidence_trend="decreasing")

	def _mock_score(_payload, _chain_health):
		return (
			RootCauseScore(actionability=2, system_depth=2, recurrence_prevention=1, total=5),
			LoopSignals(
				fmea_gap=False,
				degraded=True,
				boundary_crossed=False,
				team_cannot_fix=False,
				alignment="weak",
				assessed_confidence=0.51,
			),
		)

	monkeypatch.setattr(nodes, "evaluate_chain_health", _mock_chain_health)
	monkeypatch.setattr(nodes, "score_root_cause", _mock_score)

	agent = LoopControlAgent()
	output = agent.evaluate(_build_input("Repeated non-specific cause wording", loop=4, confidence=0.52))

	assert output["decision"] == "STOP_DEGRADED"
	assert output["next_step"] is None
