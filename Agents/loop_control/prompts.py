"""
Prompt builders for Loop Control LLM-assisted checks.

Single unified assessment prompt for pharmaceutical 5-Why RCA.
One call answers: system depth, actionability, recurrence prevention,
incident alignment, and next-probe direction simultaneously.
"""


def build_unified_assessment_prompt(
	incident_description: str,
	current_cause: str,
	full_chain: list[str],
	current_confidence: float,
	loop_count: int,
	max_loops: int,
) -> str:
	chain_text = (
		"\n".join(f"  Loop {i + 1}: {c}" for i, c in enumerate(full_chain))
		if full_chain
		else "  (no prior why-chain items yet)"
	)
	return (
		"You are the loop-control evaluator for pharmaceutical manufacturing 5-Why root cause analysis.\n"
		"Decide whether the current cause is the true root cause, or whether another Why loop is needed.\n"
		"Do NOT request more context. Evaluate from the chain and incident provided.\n\n"
		"Return ONLY valid JSON — no markdown, no explanation — with this exact schema:\n"
		"{\n"
		'  "is_root_cause": boolean,\n'
		'  "system_depth": 1 | 2 | 3,\n'
		'  "actionability": 1 | 2 | 3,\n'
		'  "recurrence_prevention": "full" | "partial" | "none",\n'
		'  "incident_alignment": "strong" | "weak" | "none",\n'
		'  "confidence": float between 0.0 and 1.0,\n'
		'  "rationale": string (2-3 sentences, evidence-based),\n'
		'  "probe_angle": "training" | "process" | "sop_procedure" | "equipment" | "material" | "detection_control" | "governance",\n'
		'  "next_question_hint": string (the specific next why-question to ask if another loop is needed)\n'
		"}\n\n"
		"SCORING GUIDE — pharmaceutical manufacturing 5-Why:\n\n"
		"system_depth:\n"
		"  1 = Local physical/chemical parameter or isolated operator action\n"
		"      (temperature dropped, speed out of range, sensor drifted, wrong button pressed)\n"
		"  2 = Component or process-step failure — a specific step, material, or sub-system failed\n"
		"      (coating pan speed inconsistent, wrong granulation endpoint used, incorrect material lot)\n"
		"  3 = Systemic gap — the failure is rooted in how the SYSTEM is designed or governed:\n"
		"      SOP content flaw, training program gap, validation strategy gap, QMS workflow design,\n"
		"      change-control weakness, process design flaw, governance/ownership absence\n"
		"  RULE: Training gaps ('operator not trained on X'), SOP design gaps, validation gaps,\n"
		"        governance gaps are ALL system_depth=3 — they describe system-level control failures.\n\n"
		"actionability:\n"
		"  1 = CAPA cannot directly address this (external supplier, force-majeure, genuinely unknown)\n"
		"  2 = CAPA can partially close (add a monitoring step, update one SOP section)\n"
		"  3 = CAPA can fully close the gap (redesign training program, implement automated detection,\n"
		"      redesign workflow, add mandatory verification, revise validation protocol)\n\n"
		"recurrence_prevention:\n"
		'  "full"    = Fixing this makes the identical incident MECHANICALLY IMPOSSIBLE to recur.\n'
		"              The absent control now exists and no alternative pathway to the same failure remains.\n"
		"              Example: no validated parameters existed → now validated and in SOP → control is mechanically present.\n"
		'  "partial" = Fixing this significantly reduces likelihood but does NOT eliminate all pathways.\n'
		"              Use 'partial' when: (a) the cause describes organizational pressure or behavioral tendency\n"
		"              (production pressure, alarm fatigue, time pressure, workload) — reducing pressure helps\n"
		"              but cannot mechanically guarantee the behavior will not recur via other pressures;\n"
		"              (b) fixing this removes one pathway but a second pathway to the same incident still exists.\n"
		'  "none"    = Fixing this does not prevent the incident from recurring.\n'
		"  CRITICAL: 'full' requires that after the fix, the incident pathway is structurally closed.\n"
		"             If the cause is a PRESSURE or TENDENCY (production pressure, alarm fatigue,\n"
		"             operator habit, workload) rather than an ABSENT CONTROL (no SOP, no validation,\n"
		"             no procedure, no limits defined) — the answer is 'partial', not 'full'.\n"
		"  NOTE: This asks about FUTURE RECURRENCE of the incident, not about the prior chain items.\n\n"
		"incident_alignment:\n"
		'  "strong" = Directly fixing this cause prevents the specific batch/complaint described\n'
		'  "weak"   = Indirect or partial connection — some linkage but not certain\n'
		'  "none"   = Fixing this cause would not address the described incident\n\n'
		"ROOT-CAUSE RULES (mandatory — enforce these before setting is_root_cause=true):\n"
		"1. is_root_cause=true REQUIRES ALL of:\n"
		"   - system_depth = 3\n"
		"   - recurrence_prevention in [full, partial]\n"
		"   - incident_alignment != none\n"
		"2. Local parameter conditions (temperature, pressure, speed, coating weight): system_depth <= 2\n"
		"   UNLESS the cause text explicitly names the upstream SOP/training/process design failure.\n"
		"3. 'Operator was not trained on X' WITH a specific knowledge/procedure gap = system_depth=3\n"
		"   (this is a training program design failure, not an individual operator error)\n"
		"4. 'Operator made an error' WITHOUT naming WHY = system_depth=1 (still a symptom)\n"
		"5. probe_angle and next_question_hint are the guidance for the NEXT why-question.\n"
		"   next_question_hint must be a concrete, specific question (not generic) that probes deeper.\n\n"
		"CALIBRATION EXAMPLES:\n"
		"- 'Inlet temperature dropped to 52°C during coating' → system_depth=1, is_root_cause=false\n"
		"  next hint: Why did the inlet temperature drop — equipment fault, control setting, or operator action?\n"
		"- 'Coating pan speed and temperature parameters were not validated for this batch size'\n"
		"  → system_depth=3, recurrence_prevention='full', is_root_cause=true\n"
		"  (absent control: no validated limits → adding them closes the pathway mechanically)\n"
		"- 'Operator was not adequately trained on inlet temperature and pan speed alarm responses'\n"
		"  → system_depth=3, recurrence_prevention='full', is_root_cause=true\n"
		"  (absent control: training program gap — redesigning the program closes the pathway)\n"
		"- 'High production pressure and tight shift schedules cause alarm fatigue, prompting operators\n"
		"   to dismiss alarms to maintain throughput'\n"
		"  → system_depth=3 (governance/organizational gap), recurrence_prevention='partial', is_root_cause=false\n"
		"  WHY partial: reducing production pressure reduces alarm fatigue, but cannot mechanically prevent\n"
		"  alarm dismissal — other pressures or habits could still cause the same behavior. The absent\n"
		"  control (formal alarm management SOP, mandatory escalation procedure) has not been named yet.\n"
		"  next hint: Why does no formal alarm management procedure exist to mandate escalation response?\n"
		"- 'Line clearance checks were inconsistently performed' → system_depth=2\n"
		"  next hint: Why were line clearance checks inconsistent — missing SOP step, no enforcement, or training gap?\n"
		"- 'No formal change-control procedure for cleaning protocol updates' → system_depth=3,\n"
		"  recurrence_prevention='full', is_root_cause=true (absent control — adding the procedure closes the gap)\n\n"
		f"INCIDENT DESCRIPTION:\n{incident_description}\n\n"
		f"FULL WHY-CHAIN (oldest first):\n{chain_text}\n\n"
		f"CURRENT CAUSE TO EVALUATE:\n{current_cause}\n\n"
		f"Upstream confidence score: {current_confidence}\n"
		f"Loop position: {loop_count} of {max_loops}"
	)


def build_next_step_prompt(
	current_cause: str,
	prior_causes: list[str],
	incident_description: str,
	probe_angle: str = "process",
) -> str:
	"""Focused next-step probe — only called when unified assessment hint is unavailable."""
	prior_text = (
		"\n".join(f"  - {c}" for c in prior_causes) if prior_causes else "  (none yet)"
	)
	valid_angles = "training | process | sop_procedure | equipment | material | detection_control | governance"
	return (
		"Generate the next pharmaceutical 5-Why probing direction.\n"
		"Return ONLY valid JSON with this exact schema:\n"
		'{"probe_angle": string, "avoid": string, "evidence_hint": string}\n\n'
		f"probe_angle must be one of: {valid_angles}\n"
		"avoid: summarize already-covered angles so the next question does not repeat them.\n"
		"evidence_hint: name a specific pharma artifact — batch record, validation report,\n"
		"  training matrix, SOP revision log, deviation record, equipment logbook, QMS ticket.\n\n"
		f"Incident:\n{incident_description}\n\n"
		f"Current cause:\n{current_cause}\n\n"
		f"Prior causes already covered:\n{prior_text}\n\n"
		f"Suggested probe angle: {probe_angle}"
	)

