"""
Processing nodes for Loop Control agent.
"""

from Agents.loop_control.logger import log_error, log_node_end, log_node_start
from Agents.loop_control.state import LoopControlOutput, LoopControlState
from Agents.loop_control.utils import decide, evaluate_chain_health, score_root_cause


def evaluate_chain_node(state: LoopControlState) -> dict:
	"""
	Node 1: Evaluate chain quality trends and root-cause score.
	"""
	log_node_start("evaluate_chain_node")

	chain_health = evaluate_chain_health(state.input)
	root_score, loop_signals = score_root_cause(state.input, chain_health)

	log_node_end(
		"evaluate_chain_node",
		(
			f"circular={chain_health.circular}, specificity={chain_health.specificity_trend}, "
			f"confidence={chain_health.confidence_trend}, score_total={root_score.total}, "
			f"degraded={loop_signals.degraded}, alignment={loop_signals.alignment}, "
			f"fmea_gap={loop_signals.fmea_gap}"
		),
	)

	return {
		"chain_health": chain_health,
		"root_cause_score": root_score,
		"loop_signals": loop_signals,
	}


def decide_node(state: LoopControlState) -> dict:
	"""
	Node 2: Apply mandatory decision policy.
	"""
	log_node_start("decide_node")

	if state.chain_health is None or state.root_cause_score is None or state.loop_signals is None:
		msg = "State guard failed before decision: chain_health, root_cause_score, or loop_signals is missing"
		log_error("decide_node", msg)
		raise ValueError(msg)

	decision, reasoning, next_step = decide(state.input, state.chain_health, state.root_cause_score, state.loop_signals)

	log_node_end("decide_node", f"decision={decision}")
	return {
		"decision": decision,
		"reasoning": reasoning,
		"next_step": next_step,
	}


def finalize_output_node(state: LoopControlState) -> dict:
	"""
	Node 3: Build final strict output model.
	"""
	log_node_start("finalize_output_node")

	if state.decision is None or state.reasoning is None:
		msg = "State guard failed before finalize: decision or reasoning is missing"
		log_error("finalize_output_node", msg)
		raise ValueError(msg)

	if state.chain_health is None or state.root_cause_score is None:
		msg = "State guard failed before finalize: chain_health or root_cause_score is missing"
		log_error("finalize_output_node", msg)
		raise ValueError(msg)

	output = LoopControlOutput(
		decision=state.decision,
		reasoning=state.reasoning,
		chain_health=state.chain_health,
		root_cause_score=state.root_cause_score,
		next_step=state.next_step if state.decision == "LOOP" else None,
	)

	log_node_end("finalize_output_node", "final output generated")
	return {"final_output": output}

