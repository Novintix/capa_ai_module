"""
Core logic for Loop Control decisions — pharmaceutical 5-Why RCA.

Architecture
------------
1. evaluate_chain_health  — trend analysis + circularity check (includes current cause)
2. score_root_cause       — ONE unified LLM call, no keyword post-processing
3. decide                 — deterministic gate logic; LLM hint reused for next-step direction

Key design decisions
--------------------
- _calibrate_system_depth() removed: the LLM assigns system_depth; keyword override caused the
  training-gap bug ("temperature" in cause text clamped depth to 2).
- recurrence_prevention now asks "prevents future recurrence?" (full/partial/none → 3/2/1)
  instead of the old "makes prior chain impossible?" (chain_resolution).
- assessed_confidence = LLM confidence (not max(input, llm) — that inflated scores).
- evaluate_chain_health includes current_top_cause + current_cause_confidence in trends.
- is_circular compares current cause against ALL chain causes, not chain[:-1].
"""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from math import sqrt
from typing import Any

from Agents.loop_control.prompts import (
	build_unified_assessment_prompt,
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

# Pharma probe angles — replaces old IT-centric PROBE_ANGLES
PHARMA_PROBE_ANGLES = {
	"training", "process", "sop_procedure", "equipment",
	"material", "detection_control", "governance",
}

# Fallback-only term sets (used only when LLM is unavailable)
PHARMA_SYSTEMIC_TERMS = {
	"sop", "procedure", "protocol", "training", "validation", "qualification",
	"change control", "qms", "governance", "policy", "process design", "standard work",
	"work instruction", "specification", "deviation", "oversight", "audit",
	"review", "verification", "monitoring", "enforcement", "accountability",
}

PHARMA_SPECIFIC_TERMS = {
	"coating", "granulation", "compression", "dissolution", "tablet", "batch",
	"inlet", "pan speed", "humidity", "film weight", "hardness", "friability",
	"moisture", "pressure", "flow", "blend", "excipient", "api",
	"calibration", "cleaning", "spray rate", "nozzle", "equipment",
}

LOCAL_CONDITION_TERMS = {
	"temperature", "pressure", "speed", "flow", "drift", "threshold",
	"calibration drift", "signal", "noise", "voltage", "moisture level",
	"parameter out", "sensor", "module fault",
}

TRAINING_GAP_TERMS = {
	"not trained", "training gap", "insufficient training", "competency gap",
	"qualification gap", "retraining", "training matrix", "knowledge transfer",
	"inadequate training", "not adequately trained",
}

SYMPTOM_ONLY_TERMS = {
	"operator error", "human error", "careless", "mistake", "forgot",
}

ABSTRACT_NOUNS = {
	"issue", "problem", "thing", "factor", "challenge", "condition",
	"situation", "error", "concern",
}

MIN_CONFIDENCE_FOR_ROOT = 0.65
MIN_LOOPS_FOR_DEGRADED_STOP = 3


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
	"""Pharma-aware specificity score (0-1). Higher = more specific and systemic."""
	cause_lower = cause.lower()
	tokens = _tokenize(cause_lower)

	systemic_hits = sum(1 for term in PHARMA_SYSTEMIC_TERMS if term in cause_lower)
	specific_hits = sum(1 for term in PHARMA_SPECIFIC_TERMS if term in cause_lower)
	training_hits = sum(1 for term in TRAINING_GAP_TERMS if term in cause_lower)
	number_bonus = 1 if re.search(r"\b\d+(?:\.\d+)?\b", cause) else 0
	length_bonus = min(len(tokens) / 12.0, 1.0)
	abstract_hits = sum(1 for term in ABSTRACT_NOUNS if term in cause_lower)

	score = (
		0.30 * min((systemic_hits + training_hits) / 2.0, 1.0)
		+ 0.20 * min(specific_hits / 2.0, 1.0)
		+ 0.15 * number_bonus
		+ 0.20 * length_bonus
		- 0.20 * min(abstract_hits / 2.0, 1.0)
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


def specificity_trend(all_causes: list[str]) -> str:
	"""Trend across all causes. Pass the full list including current_top_cause."""
	scores = [_specificity_score(c) for c in all_causes if c]
	return _trend_from_series(scores)


def confidence_trend(all_confidences: list[float]) -> str:
	"""Trend across all confidences. Pass the full list including current_cause_confidence."""
	scores = [float(c) for c in all_confidences if c is not None]
	return _trend_from_series(scores, stable_threshold=0.04)


def evaluate_chain_health(agent_input: LoopControlInput) -> ChainHealth:
	"""
	Evaluate chain trends including current_top_cause as the latest data point.

	Bug fixes vs. old version:
	- Includes current_top_cause + current_cause_confidence in trend series (was excluded).
	- is_circular checks against ALL prior chain causes, not chain[:-1] (was empty for single-item chains).
	"""
	chain_items = [item.model_dump() for item in agent_input.full_why_chain]
	prior_causes = [item["cause"] for item in chain_items]
	prior_confidences = [item["confidence"] for item in chain_items]

	# Include current cause as the latest point in both trend series
	all_causes = prior_causes + [agent_input.current_top_cause]
	all_confidences = prior_confidences + [agent_input.current_cause_confidence]

	# Circularity: some clients include the current loop's result in full_why_chain.
	# Exclude the last chain item if it is essentially identical to current_top_cause
	# (self-circular false positive when loop=1 and chain has exactly that one item).
	if prior_causes and text_similarity(prior_causes[-1], agent_input.current_top_cause) > 0.85:
		causes_for_circular_check = prior_causes[:-1]
	else:
		causes_for_circular_check = prior_causes
	circular = is_circular(agent_input.current_top_cause, causes_for_circular_check)

	return ChainHealth(
		circular=circular,
		specificity_trend=specificity_trend(all_causes),
		confidence_trend=confidence_trend(all_confidences),
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



# ---------------------------------------------------------------------------
# Root cause assessment
# ---------------------------------------------------------------------------

def _pharma_probe_angle(text_lower: str) -> str:
	"""Choose the most contextually appropriate next-probe direction."""
	if any(t in text_lower for t in {"train", "competenc", "qualif", "skill", "knowledge"}):
		return "training"
	if any(t in text_lower for t in {"sop", "procedure", "protocol", "work instruction"}):
		return "sop_procedure"
	if any(t in text_lower for t in {"govern", "policy", "oversight", "qms", "change control"}):
		return "governance"
	if any(t in text_lower for t in {"equipment", "machine", "device", "instrument", "calibr"}):
		return "equipment"
	if any(t in text_lower for t in {"material", "excipient", "api", "ingredient", "lot"}):
		return "material"
	if any(t in text_lower for t in {"detect", "monitor", "alert", "inspect", "test"}):
		return "detection_control"
	return "process"


def _fallback_root_assessment(agent_input: LoopControlInput, chain_health: ChainHealth) -> dict[str, Any]:
	"""Keyword-based fallback when LLM is completely unavailable."""
	cause = agent_input.current_top_cause
	cause_lower = cause.lower()

	is_systemic = any(term in cause_lower for term in PHARMA_SYSTEMIC_TERMS)
	is_training_gap = any(term in cause_lower for term in TRAINING_GAP_TERMS)
	is_local = (
		any(term in cause_lower for term in LOCAL_CONDITION_TERMS)
		and not is_systemic
		and not is_training_gap
	)
	is_symptom_only = any(term in cause_lower for term in SYMPTOM_ONLY_TERMS) and not is_systemic

	if is_symptom_only:
		system_depth = 1
	elif is_local:
		system_depth = 1
	elif is_systemic or is_training_gap:
		system_depth = 3
	else:
		system_depth = 2

	actionability = 3 if (is_systemic or is_training_gap) else 2
	if any(w in cause_lower for w in {"unknown", "unclear", "possibly", "maybe"}):
		actionability = 1

	recurrence_score = 3 if system_depth == 3 else (2 if system_depth == 2 else 1)
	recurrence_label = {3: "full", 2: "partial", 1: "none"}[recurrence_score]

	incident_sim = text_similarity(cause, agent_input.incident_description)
	if incident_sim >= 0.20:
		alignment = "strong"
	elif incident_sim >= 0.08:
		alignment = "weak"
	else:
		alignment = "none"

	is_root = system_depth >= 3 and recurrence_score == 3 and alignment == "strong"
	return {
		"is_root_cause": is_root,
		"actionability": actionability,
		"system_depth": system_depth,
		"recurrence_prevention": recurrence_score,
		"recurrence_str": recurrence_label,
		"alignment": alignment,
		"model_confidence": agent_input.current_cause_confidence,
		"rationale": "Keyword-based fallback assessment (LLM unavailable).",
		"probe_angle": _pharma_probe_angle(cause_lower),
		"next_question_hint": "",
	}


def _assess_root_cause(agent_input: LoopControlInput) -> dict[str, Any]:
	"""Single unified LLM call covering all scoring dimensions at once."""
	full_chain = [item.cause for item in agent_input.full_why_chain if item.cause]
	prompt = build_unified_assessment_prompt(
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

	recurrence_raw = str(result.get("recurrence_prevention", "partial")).lower().strip()
	if recurrence_raw not in {"full", "partial", "none"}:
		recurrence_raw = "partial"
	recurrence_score = {"full": 3, "partial": 2, "none": 1}[recurrence_raw]

	alignment = str(result.get("incident_alignment", "weak")).lower().strip()
	if alignment not in {"strong", "weak", "none"}:
		alignment = "weak"

	try:
		model_confidence = float(result.get("confidence", agent_input.current_cause_confidence))
	except (TypeError, ValueError):
		model_confidence = agent_input.current_cause_confidence
	model_confidence = max(0.0, min(1.0, model_confidence))

	probe_angle = str(result.get("probe_angle", "process")).lower().strip()
	if probe_angle not in PHARMA_PROBE_ANGLES:
		probe_angle = _pharma_probe_angle(agent_input.current_top_cause.lower())

	return {
		"is_root_cause": bool(result.get("is_root_cause", False)),
		"actionability": actionability,
		"system_depth": system_depth,
		"recurrence_prevention": recurrence_score,
		"recurrence_str": recurrence_raw,
		"alignment": alignment,
		"model_confidence": model_confidence,
		"rationale": str(result.get("rationale", "")).strip(),
		"probe_angle": probe_angle,
		"next_question_hint": str(result.get("next_question_hint", "")).strip(),
	}


def score_root_cause(
	agent_input: LoopControlInput, chain_health: ChainHealth
) -> tuple[RootCauseScore, LoopSignals]:
	"""
	Score the current cause and build LoopSignals.

	Uses a single unified LLM call. No keyword post-processing of LLM scores
	(_calibrate_system_depth removed — it was the source of the training-gap bug).
	"""
	llm_fallback = False
	llm_fallback_reason = None
	try:
		assessment = _assess_root_cause(agent_input)
	except Exception as exc:
		assessment = _fallback_root_assessment(agent_input, chain_health)
		llm_fallback = True
		llm_fallback_reason = str(exc)

	actionability = assessment["actionability"]
	system_depth = assessment["system_depth"]
	recurrence_prevention = assessment["recurrence_prevention"]
	alignment = assessment["alignment"]
	# Use LLM confidence directly — do not max() with raw input confidence (inflates scores)
	assessed_confidence = round(
		float(assessment.get("model_confidence", agent_input.current_cause_confidence)), 3
	)

	degraded = chain_health.circular and chain_health.confidence_trend == "decreasing"
	total = actionability + system_depth + recurrence_prevention

	loop_signals = LoopSignals(
		fmea_gap=False,
		degraded=degraded,
		boundary_crossed=False,
		team_cannot_fix=False,
		alignment=alignment,
		assessed_confidence=assessed_confidence,
		llm_fallback=llm_fallback,
		llm_fallback_reason=llm_fallback_reason,
		recurrence_str=assessment.get("recurrence_str", "partial"),
		probe_angle=assessment.get("probe_angle", "process"),
		next_question_hint=assessment.get("next_question_hint", ""),
		assessment_rationale=assessment.get("rationale", ""),
		llm_is_root_cause=bool(assessment.get("is_root_cause", False)),
	)

	return (
		RootCauseScore(
			actionability=actionability,
			system_depth=system_depth,
			recurrence_prevention=recurrence_prevention,
			total=total,
			recurrence_str=assessment.get("recurrence_str"),
		),
		loop_signals,
	)



# ---------------------------------------------------------------------------
# Next-step generation
# ---------------------------------------------------------------------------

def _pharma_evidence_hint(text_lower: str) -> str:
	"""Return a pharma-appropriate artifact hint based on cause/incident content."""
	if any(t in text_lower for t in {"train", "competenc", "qualif", "skill"}):
		return "Training matrix, training records, SOP for this procedure."
	if any(t in text_lower for t in {"sop", "procedure", "protocol"}):
		return "SOP document and revision history, batch record compliance check."
	if any(t in text_lower for t in {"equip", "coating", "granulat", "compress"}):
		return "Equipment qualification records, cleaning logs, PM schedule."
	if any(t in text_lower for t in {"govern", "oversight", "qms", "change control"}):
		return "QMS audit trail, deviation management log, CAPA effectiveness review."
	if any(t in text_lower for t in {"valid", "qualif", "specif"}):
		return "Validation protocol/report, process capability data, specification records."
	return "Batch record, deviation report, or process control chart for this process step."


def generate_next_step(agent_input: LoopControlInput, loop_signals: LoopSignals) -> NextStep:
	"""
	Build the next-step probe direction.

	Reuses probe_angle and next_question_hint from the unified assessment when available,
	avoiding a second LLM call. Only falls back to a separate LLM call when the hint is absent.
	"""
	prior_causes = [item.cause for item in agent_input.full_why_chain if item.cause]
	probe_angle = (loop_signals.probe_angle or "process") if loop_signals else "process"
	next_hint = (loop_signals.next_question_hint or "").strip() if loop_signals else ""
	avoid_text = (
		f"Avoid repeating already-covered causes, especially: '{prior_causes[-1]}'"
		if prior_causes
		else "Avoid restating the symptom."
	)
	combo_lower = (agent_input.current_top_cause + " " + agent_input.incident_description).lower()
	evidence_fallback = _pharma_evidence_hint(combo_lower)

	# If the unified assessment already gave us a good next question, reuse it — no extra LLM call
	if next_hint and len(next_hint) > 20:
		return NextStep(
			target=agent_input.current_top_cause,
			probe_angle=probe_angle,
			avoid=avoid_text,
			evidence_hint=next_hint,
		)

	# Secondary LLM call only when we have no hint from the unified assessment
	try:
		result = _invoke_json_prompt(
			build_next_step_prompt(
				agent_input.current_top_cause,
				prior_causes,
				agent_input.incident_description,
				probe_angle=probe_angle,
			)
		)
		pa = str(result.get("probe_angle", probe_angle)).lower().strip()
		if pa not in PHARMA_PROBE_ANGLES:
			pa = probe_angle
		avoid = str(result.get("avoid", avoid_text)).strip() or avoid_text
		eh = str(result.get("evidence_hint", evidence_fallback)).strip() or evidence_fallback
		return NextStep(target=agent_input.current_top_cause, probe_angle=pa, avoid=avoid, evidence_hint=eh)
	except Exception:
		return NextStep(
			target=agent_input.current_top_cause,
			probe_angle=probe_angle,
			avoid=avoid_text,
			evidence_hint=evidence_fallback,
		)


# ---------------------------------------------------------------------------
# Decision gate
# ---------------------------------------------------------------------------

def _root_gate(score: RootCauseScore, loop_signals: LoopSignals, confidence: float) -> bool:
	"""
	Score-based gate for root cause confirmation.

	total >= 8 (depth=3 + action>=2 + recurrence>=partial) is treated as unambiguous —
	the LLM boolean field is bypassed because absent-control causes reliably reach this
	threshold and the boolean introduces a second LLM call that is itself non-deterministic.

	Only total == 7 (depth=3, action=2, recurrence=partial — the true minimum borderline)
	requires llm_is_root_cause as a tiebreaker. This handles "contextual pressure" causes
	(alarm fatigue, production pressure) which score depth=3 + action=2 with recurrence=partial,
	giving total=7, and the LLM marks is_root_cause=false.
	"""
	base = (
		score.system_depth >= 3
		and score.actionability >= 2
		and score.recurrence_prevention >= 2
		and loop_signals.alignment != "none"
		and not loop_signals.degraded
		and confidence >= MIN_CONFIDENCE_FOR_ROOT
	)
	if not base:
		return False
	# Unambiguous (depth=3 + action>=2 + recurrence>=partial): trust scores over LLM boolean
	if score.total >= 8:
		return True
	# Borderline (total == 7 only): require LLM agreement as tiebreaker
	return loop_signals.llm_is_root_cause


def _build_loop_reasoning(score: RootCauseScore, loop_signals: LoopSignals) -> str:
	reasons = []
	if score.system_depth < 3:
		reasons.append(
			f"system_depth={score.system_depth} — need to reach the process/SOP/training/governance level (3)"
		)
	if score.actionability < 2:
		reasons.append("cause is not yet directly actionable via CAPA")
	if score.recurrence_prevention < 2:
		recurrence_label = loop_signals.recurrence_str or "none"
		reasons.append(f"recurrence prevention insufficient ('{recurrence_label}') — fixing this may not prevent reoccurrence")
	if loop_signals.alignment == "weak":
		reasons.append("incident alignment is weak — continue asking why toward direct incident prevention")
	if loop_signals.degraded:
		reasons.append("chain shows circular reasoning with declining confidence")
	# All score gates pass but LLM blocked (borderline total=7, recurrence not full)
	if not reasons and not loop_signals.llm_is_root_cause and score.total < 8:
		reasons.append(
			f"scores meet threshold (total={score.total}) but cause describes a contextual pressure "
			f"rather than a structural control gap — recurrence prevention is '{loop_signals.recurrence_str}'. "
			"Ask why this pressure exists or what specific control/procedure is absent."
		)
	if not reasons:
		reasons.append("overall evidence not yet sufficient for root-cause confirmation")
	return "Why loop recommended: " + "; ".join(reasons) + "."


def decide(
	agent_input: LoopControlInput,
	chain_health: ChainHealth,
	score: RootCauseScore,
	loop_signals: LoopSignals,
) -> tuple[str, str, NextStep | None]:
	"""
	Deterministic decision gate — returns (decision, reasoning, next_step).

	Priority order:
	1. Max loops reached
	2. Chain degraded (circular + declining confidence for MIN_LOOPS_FOR_DEGRADED_STOP+ loops)
	3. Root cause confirmed (_root_gate passes)
	4. Alignment completely lost for 2+ loops
	5. Continue looping
	"""
	loop = agent_input.current_loop_count
	max_loops = agent_input.max_loops
	confidence = loop_signals.assessed_confidence

	# 1. Max loops reached
	if loop >= max_loops:
		if _root_gate(score, loop_signals, confidence):
			depth_label = (
				"systemic process/SOP/training/governance gap"
				if score.system_depth == 3
				else "component-level issue"
			)
			return (
				"STOP_ROOT_FOUND",
				(
					f"Root cause confirmed at final loop {loop}/{max_loops}: {depth_label}. "
					f"system_depth={score.system_depth}, actionability={score.actionability}, "
					f"recurrence_prevention={loop_signals.recurrence_str}, "
					f"incident_alignment={loop_signals.alignment}, confidence={confidence}."
				),
				None,
			)
		return (
			"STOP_DEGRADED",
			(
				f"Max loops ({max_loops}) reached without confirming root cause. "
				f"Best candidate: system_depth={score.system_depth}, confidence={confidence}. "
				"Manual investigation recommended."
			),
			None,
		)

	# 2. Chain degraded
	if loop_signals.degraded and loop >= MIN_LOOPS_FOR_DEGRADED_STOP:
		return (
			"STOP_DEGRADED",
			(
				"Why-chain quality degraded: circular reasoning with declining confidence over multiple loops. "
				"Further iterations are unlikely to improve. Manual review recommended."
			),
			None,
		)

	# 3. Root cause confirmed
	if _root_gate(score, loop_signals, confidence):
		depth_label = (
			"systemic process/SOP/training/governance gap"
			if score.system_depth == 3
			else "component-level issue"
		)
		return (
			"STOP_ROOT_FOUND",
			(
				f"Root cause confirmed: {depth_label}. "
				f"system_depth={score.system_depth}, actionability={score.actionability}, "
				f"recurrence_prevention={loop_signals.recurrence_str}, "
				f"incident_alignment={loop_signals.alignment}, confidence={confidence}."
			),
			None,
		)

	# 4. Alignment completely lost for multiple loops
	if loop_signals.alignment == "none" and loop >= 2:
		return (
			"STOP_DEGRADED",
			(
				f"Current cause has no alignment with the original incident after {loop} loops. "
				"The chain has drifted from the incident context. Manual escalation recommended."
			),
			None,
		)

	# 5. Continue looping
	return (
		"LOOP",
		_build_loop_reasoning(score, loop_signals),
		generate_next_step(agent_input, loop_signals),
	)

