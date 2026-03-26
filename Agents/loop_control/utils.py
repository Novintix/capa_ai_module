"""
Core logic for Loop Control decisions.

Decisioning remains deterministic; selected signals are LLM-assisted with strict JSON parsing.
"""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from math import sqrt
from typing import Any

from Agents.loop_control.prompts import (
	build_root_assessment_prompt,
	build_next_step_prompt,
)
from Agents.loop_control.state import (
	ChainHealth,
	LoopControlInput,
	LoopSignals,
	NextStep,
	RootCauseScore,
)
from config.aws_bedrock_config import get_llm


STOPWORDS = {
	"a", "an", "the", "is", "are", "was", "were", "be", "to", "of", "for", "in",
	"on", "at", "by", "with", "from", "and", "or", "that", "this", "it", "as",
	"due", "because", "issue", "problem", "cause", "caused",
}

VAGUE_TERMS = {
	"issue", "problem", "error", "mistake", "failure", "unknown", "misc", "general",
	"thing", "stuff", "bad", "not good", "concern",
}

SYSTEMIC_TERMS = {
	"process", "procedure", "policy", "design", "system", "training", "validation",
	"control", "workflow", "governance", "specification", "standard", "protocol",
}

ACTIONABLE_TERMS = {
	"implement", "update", "revise", "automate", "calibrate", "replace", "validate",
	"train", "monitor", "enforce", "redesign", "introduce", "define", "establish",
}

SYMPTOM_TERMS = {
	"operator", "human", "careless", "forgot", "typo", "accident", "symptom",
}

PREVENTION_TERMS = {
	"prevent", "recurrence", "system", "control", "verification", "audit", "training",
	"design", "policy", "procedure", "monitoring", "mistake-proof",
}

COMPONENT_TERMS = {
	"sensor", "valve", "pump", "controller", "service", "module", "api", "interface",
	"pipeline", "batch", "job", "queue", "schema", "database", "firmware", "server",
}

CONFIG_TERMS = {
	"config", "configuration", "setting", "parameter", "threshold", "timeout", "limit",
	"version", "flag", "key", "profile", "sop", "procedure",
}

ABSTRACT_NOUNS = {
	"issue", "problem", "thing", "factor", "challenge", "condition", "situation", "error",
	"quality", "performance", "concern", "environment",
}

PROBE_ANGLES = {"configuration", "detection", "change", "load", "process"}

SYSTEM_ROOT_TERMS = {
	"process", "policy", "sop", "standard work", "work instruction", "procedure",
	"change control", "governance", "ownership", "training system", "design control",
	"management review", "validation strategy", "release criteria",
}

SYMPTOM_ONLY_TERMS = {
	"operator error", "human error", "careless", "mistake", "forgot", "typo",
}

LOCAL_CONDITION_TERMS = {
	"temperature", "pressure", "speed", "flow", "drift", "setting", "threshold",
	"calibration", "signal", "noise", "voltage", "heater", "sensor", "module fault",
}


def _tokenize(text: str) -> set[str]:
	clean = "".join(ch.lower() if (ch.isalnum() or ch.isspace()) else " " for ch in text)
	tokens = [tok for tok in clean.split() if tok and tok not in STOPWORDS and len(tok) > 2]
	return set(tokens)


def text_similarity(a: str, b: str) -> float:
	"""
	Heuristic semantic similarity that blends token overlap and sequence ratio.
	"""
	a_tokens = _tokenize(a)
	b_tokens = _tokenize(b)

	if not a_tokens and not b_tokens:
		return 1.0
	if not a_tokens or not b_tokens:
		return 0.0

	intersection = len(a_tokens & b_tokens)
	union = len(a_tokens | b_tokens)
	jaccard = intersection / union if union else 0.0
	seq_ratio = SequenceMatcher(None, a.lower(), b.lower()).ratio()

	return (0.65 * jaccard) + (0.35 * seq_ratio)


def _overlap_ratio(terms_a: set[str], terms_b: set[str]) -> float:
	if not terms_a or not terms_b:
		return 0.0
	return len(terms_a & terms_b) / max(1, min(len(terms_a), len(terms_b)))


def is_circular(current_top_cause: str, previous_causes: list[str], threshold: float = 0.55) -> bool:
	if not previous_causes:
		return False

	current_terms = _tokenize(current_top_cause)
	for previous in previous_causes:
		previous_terms = _tokenize(previous)
		if _overlap_ratio(current_terms, previous_terms) > threshold:
			return True
	return False


def _specificity_score(cause: str) -> float:
	cause_lower = cause.lower()
	tokens = _tokenize(cause_lower)

	component_hits = sum(1 for term in COMPONENT_TERMS if term in cause_lower)
	config_hits = sum(1 for term in CONFIG_TERMS if term in cause_lower)
	abstract_hits = sum(1 for term in ABSTRACT_NOUNS if term in cause_lower)
	number_bonus = 1 if re.search(r"\b\d+(?:\.\d+)?\b", cause) else 0
	length_bonus = min(len(tokens) / 16.0, 1.0)

	score = (
		(0.25 * length_bonus)
		+ (0.30 * min(component_hits / 2.0, 1.0))
		+ (0.30 * min(config_hits / 2.0, 1.0))
		+ (0.15 * number_bonus)
		- (0.35 * min(abstract_hits / 2.0, 1.0))
	)
	return max(0.0, min(1.0, score))


def _trend_from_series(values: list[float], stable_threshold: float = 0.03) -> str:
	if len(values) <= 1:
		return "stable"

	x = list(range(len(values)))
	mean_x = sum(x) / len(x)
	mean_y = sum(values) / len(values)
	numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, values))
	denominator = sqrt(sum((xi - mean_x) ** 2 for xi in x) * sum((yi - mean_y) ** 2 for yi in values))

	if denominator == 0:
		slope = 0.0
	else:
		slope = numerator / denominator

	if slope > stable_threshold:
		return "increasing"
	if slope < -stable_threshold:
		return "decreasing"
	return "stable"


def specificity_trend(full_why_chain: list[dict]) -> str:
	causes = [item["cause"] for item in full_why_chain if item.get("cause")]
	scores = [_specificity_score(cause) for cause in causes]
	return _trend_from_series(scores)


def confidence_trend(full_why_chain: list[dict]) -> str:
	scores = [float(item["confidence"]) for item in full_why_chain if item.get("confidence") is not None]
	return _trend_from_series(scores, stable_threshold=0.04)


def evaluate_chain_health(agent_input: LoopControlInput) -> ChainHealth:
	chain_items = [item.model_dump() for item in agent_input.full_why_chain]
	previous_causes = [item["cause"] for item in chain_items[:-1]]

	circular = is_circular(agent_input.current_top_cause, previous_causes)
	specificity = specificity_trend(chain_items)
	confidence = confidence_trend(chain_items)

	return ChainHealth(
		circular=circular,
		specificity_trend=specificity,
		confidence_trend=confidence,
	)


def _extract_json_object(raw: str) -> dict[str, Any]:
	cleaned = re.sub(r"```(?:json)?", "", raw, flags=re.IGNORECASE).replace("```", "").strip()
	cleaned = re.sub(r"<reasoning>.*?</reasoning>", "", cleaned, flags=re.DOTALL).strip()

	try:
		parsed = json.loads(cleaned)
		if isinstance(parsed, dict):
			return parsed
	except json.JSONDecodeError:
		pass

	match = re.search(r"\{.*\}", cleaned, re.DOTALL)
	if not match:
		raise ValueError("No JSON object found in LLM response")

	parsed = json.loads(match.group())
	if not isinstance(parsed, dict):
		raise ValueError("LLM JSON payload must be an object")
	return parsed


def _invoke_json_prompt(prompt: str) -> dict[str, Any]:
	llm = get_llm()
	response = llm.invoke(prompt)
	return _extract_json_object(response.content)


def _clamp_score_band(value: Any, default: int = 2) -> int:
	try:
		as_int = int(value)
	except (TypeError, ValueError):
		return default
	return min(3, max(1, as_int))



def _assess_root_cause(agent_input: LoopControlInput) -> dict[str, Any]:
	full_chain = [item.cause for item in agent_input.full_why_chain if item.cause]
	prompt = build_root_assessment_prompt(
		incident_description=agent_input.incident_description,
		current_cause=agent_input.current_top_cause,
		full_chain=full_chain,
		current_confidence=agent_input.current_cause_confidence,
		loop_count=agent_input.current_loop_count,
		max_loops=agent_input.max_loops,
	)
	result = _invoke_json_prompt(prompt)

	actionability = _clamp_score_band(result.get("actionability"), default=2)
	system_depth = _clamp_score_band(result.get("system_depth"), default=2)
	chain_resolution = _clamp_score_band(result.get("chain_resolution"), default=2)
	alignment = str(result.get("incident_alignment", "weak")).lower()
	if alignment not in {"strong", "weak", "none"}:
		alignment = "weak"

	try:
		model_confidence = float(result.get("confidence", agent_input.current_cause_confidence))
	except (TypeError, ValueError):
		model_confidence = agent_input.current_cause_confidence
	model_confidence = max(0.0, min(1.0, model_confidence))

	return {
		"is_root_cause": bool(result.get("is_root_cause", False)),
		"actionability": actionability,
		"system_depth": system_depth,
		"chain_resolution": chain_resolution,
		"alignment": alignment,
		"model_confidence": model_confidence,
		"rationale": str(result.get("rationale", "")).strip(),
	}


def _calibrate_system_depth(cause: str, model_depth: int) -> int:
	cause_lower = cause.lower()

	if any(term in cause_lower for term in SYSTEM_ROOT_TERMS):
		return max(model_depth, 3)

	# Local physical/parameter conditions are not systemic root depth unless linked to governance/process terms.
	if any(term in cause_lower for term in LOCAL_CONDITION_TERMS):
		return min(model_depth, 2)

	if any(term in cause_lower for term in SYMPTOM_ONLY_TERMS):
		return min(model_depth, 1)

	return model_depth


def score_root_cause(agent_input: LoopControlInput, chain_health: ChainHealth) -> tuple[RootCauseScore, LoopSignals]:
	assessment = _assess_root_cause(agent_input)
	actionability = assessment["actionability"]
	system_depth = _calibrate_system_depth(agent_input.current_top_cause, assessment["system_depth"])
	recurrence_prevention = assessment["chain_resolution"]
	alignment = assessment["alignment"]

	degraded = chain_health.circular and chain_health.specificity_trend == "decreasing"
	total = actionability + system_depth + recurrence_prevention

	loop_signals = LoopSignals(
		fmea_gap=False,
		degraded=degraded,
		boundary_crossed=False,
		team_cannot_fix=False,
		alignment=alignment,
		llm_fallback=False,
		llm_fallback_reason=None,
	)

	return (
		RootCauseScore(
			actionability=actionability,
			system_depth=system_depth,
			recurrence_prevention=recurrence_prevention,
			total=total,
		),
		loop_signals,
	)


def _fallback_probe_angle(agent_input: LoopControlInput) -> str:
	text = f"{agent_input.current_top_cause} {agent_input.incident_description}".lower()
	if any(term in text for term in {"config", "setting", "threshold", "parameter", "version"}):
		return "configuration"
	if any(term in text for term in {"monitor", "alert", "detect", "inspection", "test"}):
		return "detection"
	if any(term in text for term in {"change", "release", "deploy", "modify", "update"}):
		return "change"
	if any(term in text for term in {"load", "volume", "throughput", "traffic", "capacity"}):
		return "load"
	return "process"


def generate_next_step(agent_input: LoopControlInput) -> NextStep:
	previous_causes = [item.cause for item in agent_input.full_why_chain[:-1] if item.cause]
	default_step = NextStep(
		target=agent_input.current_top_cause,
		probe_angle=_fallback_probe_angle(agent_input),
		avoid=(
			"Avoid repeating already-covered symptom statements and prior cause wording."
			if not previous_causes
			else f"Avoid re-asking: {previous_causes[-1]}"
		),
		evidence_hint="Gather one concrete artifact: specific log line, metric trend, config key, or SOP revision record.",
	)

	try:
		result = _invoke_json_prompt(
			build_next_step_prompt(
				agent_input.current_top_cause,
				previous_causes,
				agent_input.incident_description,
			)
		)
		probe_angle = str(result.get("probe_angle", default_step.probe_angle)).lower()
		if probe_angle not in PROBE_ANGLES:
			probe_angle = default_step.probe_angle

		avoid = str(result.get("avoid", default_step.avoid)).strip() or default_step.avoid
		evidence_hint = str(result.get("evidence_hint", default_step.evidence_hint)).strip() or default_step.evidence_hint

		return NextStep(
			target=agent_input.current_top_cause,
			probe_angle=probe_angle,
			avoid=avoid,
			evidence_hint=evidence_hint,
		)
	except Exception:
		return default_step


def decide(
	agent_input: LoopControlInput,
	chain_health: ChainHealth,
	score: RootCauseScore,
	loop_signals: LoopSignals,
) -> tuple[str, str, NextStep | None]:
	"""
	Root decision policy: return STOP_ROOT_FOUND when current cause is sufficiently systemic,
	resolves prior chain, and is aligned to incident prevention; otherwise LOOP.
	"""
	# Degradation requires both circularity and worsening specificity.
	if loop_signals.degraded:
		return (
			"LOOP",
			"Why-chain degraded: circular reasoning with decreasing specificity.",
			generate_next_step(agent_input),
		)

	# Incident drift check.
	if loop_signals.alignment == "none":
		return (
			"LOOP",
			"Cause is not aligned to preventing the original incident.",
			generate_next_step(agent_input),
		)

	adjusted_total = score.total - (1 if loop_signals.alignment == "weak" else 0)
	# Root finding must be systemic, not just a local/component-level fix.
	root_gate = (
		score.system_depth >= 3
		and score.recurrence_prevention >= 2
		and score.actionability >= 2
	)

	if root_gate and (adjusted_total >= 7 and agent_input.current_cause_confidence >= 0.7):
		return (
			"STOP_ROOT_FOUND",
			"Current cause is sufficiently deep, actionable, and chain-resolving to be treated as root cause.",
			None,
		)

	if score.system_depth >= 3 and score.recurrence_prevention >= 3 and loop_signals.alignment == "strong":
		return (
			"STOP_ROOT_FOUND",
			"Current cause is a systemic process/policy/SOP-level flaw that fully resolves prior chain causes.",
			None,
		)

	if adjusted_total <= 6:
		return (
			"LOOP",
			"Current cause is not yet strong enough as a true root cause; continue Why loop.",
			generate_next_step(agent_input),
		)

	return (
		"LOOP",
		"Another Why iteration is recommended before confirming root cause.",
		generate_next_step(agent_input),
	)

