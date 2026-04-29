"""
FastAPI router for Loop Control agent.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from Agents.loop_control.agent import LoopControlAgent
from Agents.loop_control.logger import log_error, log_request
from Agents.loop_control.state import LoopControlInput, LoopControlOutput
from agent_ops import agentops_session


router = APIRouter(prefix="/loop-control", tags=["loop-control"])
_loop_control_agent: LoopControlAgent | None = None


def get_loop_control_agent() -> LoopControlAgent:
	global _loop_control_agent
	if _loop_control_agent is None:
		_loop_control_agent = LoopControlAgent()
	return _loop_control_agent


@router.post("/analyze", response_model=LoopControlOutput)
@agentops_session(name="loop_control@router.post(_analyze, response_model=LoopControlOutput)", tags=["agents", "loop_control"])
async def analyze_loop_control(payload: LoopControlInput):
	"""
	Decide whether RCA should continue or stop based on chain quality and cause strength.
	"""
	try:
		log_request(payload)

		result_dict = get_loop_control_agent().evaluate(payload)
		output = LoopControlOutput(**result_dict)

		return JSONResponse(content=output.model_dump())
	except Exception as exc:
		log_error("router", str(exc))
		raise HTTPException(status_code=500, detail=f"Error processing loop control: {str(exc)}")
