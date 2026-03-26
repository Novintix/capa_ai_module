"""
Prompt builders for Loop Control LLM-assisted checks.

All prompts enforce JSON-only responses so downstream logic never depends on free text.
"""


def build_root_assessment_prompt(
	incident_description: str,
	current_cause: str,
	full_chain: list[str],
	current_confidence: float,
	loop_count: int,
	max_loops: int,
) -> str:
	return (
		"You are the final loop-control evaluator for 5-Why analysis.\n"
		"Your only job is to judge whether the current cause is a true root cause or whether another why-loop is needed.\n"
		"Do NOT request more context. Decide from given chain and incident only.\n\n"
		"Return ONLY valid JSON with this exact schema:\n"
		"{\"is_root_cause\": boolean, "
		"\"actionability\": 1|2|3, "
		"\"system_depth\": 1|2|3, "
		"\"chain_resolution\": 1|2|3, "
		"\"incident_alignment\": \"strong\"|\"weak\"|\"none\", "
		"\"confidence\": number, "
		"\"rationale\": string}\n\n"
		"Scoring meaning:\n"
		"- actionability: 1 cannot fix, 2 partially fixable, 3 directly fixable\n"
		"- system_depth: 1 symptom/local error, 2 component/config/control weakness, 3 process/policy/SOP/standard-work/design flaw\n"
		"- chain_resolution: 1 does not resolve prior causes, 2 resolves some, 3 makes prior causes impossible\n"
		"- incident_alignment: strong/weak/none based on prevention of the specific incident\n\n"
		"Root-cause principles you MUST apply:\n"
		"- Prefer systemic explanations over symptom restatements.\n"
		"- A strong root cause usually points to process, policy, SOP, ownership, governance, or standard-work design flaws.\n"
		"- If cause is only a local symptom with no upstream mechanism, do not mark root.\n"
		"- If fixing this cause does not prevent prior chain causes, do not mark root.\n"
		"- Keep rationale short and concrete.\n\n"
		"Hard scoring constraints (mandatory):\n"
		"- Do NOT set system_depth=3 for local condition statements such as low temperature, high pressure, unstable signal, wrong setting, drift, or component fault, unless the cause explicitly states upstream process/policy/SOP/standard-work design failure.\n"
		"- If current cause is only a parameter/component condition, system_depth must be <=2 and is_root_cause must be false.\n"
		"- is_root_cause can be true only when system_depth>=3 AND chain_resolution>=2 AND incident_alignment is not none.\n"
		"- If incident_alignment is none, is_root_cause must be false.\n"
		"- If chain_resolution=1, is_root_cause must be false.\n\n"
		"Calibration examples:\n"
		"- 'Sealing jaw temperature was slightly low' => local condition, not root by itself.\n"
		"- 'No SOP revision retraining trigger in QMS workflow' => systemic control failure, can be root.\n"
		"- 'Sensor drift observed' => local effect unless linked to missing calibration governance/process control.\n\n"
		f"Incident description:\n{incident_description}\n\n"
		f"Current cause:\n{current_cause}\n\n"
		f"Why-chain causes (oldest -> latest):\n{full_chain}\n\n"
		f"Current cause confidence: {current_confidence}\n"
		f"Loop position: {loop_count}/{max_loops}"
	)


def build_fmea_semantic_prompt(current_cause: str, known_failure_modes: list[str]) -> str:
	return (
		"You are checking whether a root-cause statement matches known FMEA failure modes.\n"
		"Return ONLY valid JSON matching this schema:\n"
		"{\"in_fmea\": boolean, \"confidence\": number, \"rationale\": string}\n"
		"Rules:\n"
		"- in_fmea=true only if the cause is materially the same as one of the known modes.\n"
		"- confidence is between 0 and 1.\n"
		"- rationale is a short plain sentence.\n\n"
		f"Current cause:\n{current_cause}\n\n"
		f"Known FMEA failure modes:\n{known_failure_modes}"
	)


def build_sop_ownership_prompt(current_cause: str, incident_description: str) -> str:
	return (
		"You are checking SOP ownership boundary in RCA.\n"
		"Return ONLY valid JSON matching this schema:\n"
		"{\"external_owner\": boolean, \"owner_type\": string, \"rationale\": string}\n"
		"owner_type should be one of: internal_team, external_vendor, customer, regulator, unknown.\n\n"
		f"Incident:\n{incident_description}\n\n"
		f"Cause statement:\n{current_cause}"
	)


def build_recurrence_prompt(current_cause: str, full_chain: list[str]) -> str:
	return (
		"You are evaluating recurrence prevention in a 5-Why RCA chain.\n"
		"Question: Would fixing the current cause make every prior cause impossible?\n"
		"Return ONLY valid JSON matching this schema:\n"
		"{\"recurrence\": \"full\"|\"partial\"|\"none\", \"rationale\": string}\n\n"
		f"Current cause:\n{current_cause}\n\n"
		f"Why-chain causes in order:\n{full_chain}"
	)


def build_alignment_prompt(current_cause: str, incident_description: str) -> str:
	return (
		"You are checking incident alignment for RCA.\n"
		"Question: Does fixing the current cause directly prevent the specific incident?\n"
		"Return ONLY valid JSON matching this schema:\n"
		"{\"alignment\": \"strong\"|\"weak\"|\"none\", \"rationale\": string}"
		f"\n\nIncident:\n{incident_description}\n\n"
		f"Cause statement:\n{current_cause}"
	)


def build_root_scoring_prompt(current_cause: str, incident_description: str) -> str:
	return (
		"Score this RCA cause for actionability and system depth in a 5-Why analysis.\n"
		"Return ONLY valid JSON matching this schema:\n"
		"{\"actionability\": 1|2|3, \"system_depth\": 1|2|3, \"rationale\": string}\n"
		"Scales:\n"
		"- actionability: 1=cannot fix, 2=partially fixable, 3=directly fixable\n"
		"- system_depth: 1=symptom, 2=component flaw, 3=process/design/policy flaw\n\n"
		"Critical scoring rules:\n"
		"- Do NOT score based on wording quality alone.\n"
		"- Favor system_depth=3 when the cause is about process, policy, SOP, governance, change-control, training system, ownership model, or standard work design.\n"
		"- Use system_depth=2 for a local technical/config/component issue that is fixable but not clearly a policy/process design flaw.\n"
		"- Use system_depth=1 only for immediate symptom/operator error statements with no upstream mechanism.\n"
		"- If the cause is a process/policy/SOP flaw and fixing it would prevent the prior why-chain from recurring, score toward root depth.\n\n"
		f"Incident:\n{incident_description}\n\n"
		f"Cause statement:\n{current_cause}"
	)


def build_next_step_prompt(current_cause: str, prior_causes: list[str], incident_description: str) -> str:
	return (
		"Generate the next 5-Why probing direction.\n"
		"Return ONLY valid JSON matching this schema:\n"
		"{\"probe_angle\": \"configuration\"|\"detection\"|\"change\"|\"load\"|\"process\", "
		"\"avoid\": string, \"evidence_hint\": string}\n"
		"Rules:\n"
		"- avoid must summarize already-covered angles.\n"
		"- evidence_hint must name concrete artifacts (specific log, metric, config key, or document).\n\n"
		f"Incident:\n{incident_description}\n\n"
		f"Current cause:\n{current_cause}\n\n"
		f"Prior causes:\n{prior_causes}"
	)

