from fastapi import APIRouter, HTTPException
from .schemas import CAPADirectorInput, CAPADirectorOutput, HumanReviewInput
from .graph import build_director_graph
from .state import DirectorState
import time

router = APIRouter(prefix="/director", tags=["CAPA Director O1"])


# ── Helper ─────────────────────────────────────────────────────────────────────

def _build_output(state: dict, awaiting: bool = False, current_node: str = None, thread_id: str = None) -> CAPADirectorOutput:
    return CAPADirectorOutput(
        thread_id                = thread_id or state.get("thread_id"),
        complaint_id             = state.get("complaint_id", "unknown"),
        risk_analysis            = state.get("risk_analysis_output"),
        rca_analysis             = state.get("rca_output"),
        action_plan              = state.get("action_plan_output"),
        effectiveness_evaluation = state.get("effectiveness_output"),
        status                   = state.get("status", "unknown"),
        error                    = state.get("error"),
        director_reasoning       = state.get("director_reasoning"),   # ← human sees WHY
        awaiting_human           = awaiting,
        current_node             = current_node,
        rca_retry_count          = state.get("rca_retry_count", 0),
        plan_retry_count         = state.get("plan_retry_count", 0),
    )


def _interrupted_node(graph, config) -> str | None:
    try:
        snapshot = graph.get_state(config)
        return snapshot.next[0] if snapshot and snapshot.next else None
    except Exception:
        return None


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/analyze", response_model=CAPADirectorOutput)
async def analyze_capa(input_data: CAPADirectorInput):
    """
    Start CAPA analysis.

    O1 Director drives the entire flow:
      - Reads RPN to decide whether to run RCA (and at what depth)
      - Re-runs RCA if confidence is LOW (up to 2 times)
      - Re-runs Action Plan if fewer than 3 actions (up to 1 time)
      - Re-runs Action Plan if Effectiveness score < 60%
      - Pauses for human review before RCA and Action Plan
        (human sees director_reasoning to know WHY O1 made the decision)
    """
    thread_id = input_data.thread_id or f"director-{input_data.complaint_id}-{int(time.time())}"
    config    = {"configurable": {"thread_id": thread_id}}
    graph     = build_director_graph(interrupt_for_human=not input_data.skip_human_review)

    initial_state = DirectorState(
        complaint_id       = input_data.complaint_id,
        complaint          = input_data.complaint,
        evidence           = input_data.evidence or "",
        sop                = input_data.sop or "",
        fmea_document_path = input_data.fmea_document_path,
        thread_id          = thread_id,
        max_rca_depth      = input_data.max_rca_depth or 5,

        containment_actions = input_data.containment_actions or "Standard containment initiated",
        timeline_constraint = input_data.timeline_constraint or "30 days",
        available_resources = input_data.available_resources or "Engineering, Quality, Production",
        system_context      = input_data.system_context or "Manufacturing Plant",

        risk_analysis_output = None,
        rca_output           = None,
        action_plan_output   = None,
        effectiveness_output = None,

        # Director brain
        next_agent          = "",
        director_reasoning  = "",
        rca_mode            = "standard",
        rca_retry_count     = 0,
        plan_retry_count    = 0,

        # Human-in-the-loop
        human_approved = None,
        human_feedback = None,

        # Error recovery
        failed_node   = None,
        retry_count   = 0,
        max_retries   = 2,
        recovery_next = None,

        status = "starting",
        error  = None,
    )

    try:
        final_state = graph.invoke(initial_state, config=config)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # Paused for human review?
    paused_at = _interrupted_node(graph, config)
    if paused_at:
        state = graph.get_state(config).values
        print(f"\n[API] ⏸  Paused before '{paused_at}'")
        print(f"[API]    Reason: {state.get('director_reasoning')}")
        print(f"[API]    Thread: {thread_id}  → POST /director/resume to continue")
        return _build_output(state, awaiting=True, current_node=paused_at, thread_id=thread_id)

    return _build_output(final_state, thread_id=thread_id)


@router.post("/resume", response_model=CAPADirectorOutput)
async def resume_capa(review: HumanReviewInput):
    """
    Resume after human review.

    The response includes director_reasoning so the reviewer knows
    exactly WHY O1 wants to run the next agent.

    approved=True  → continue to next agent
    approved=False → abort; analysis finalizes with error
    """
    config = {"configurable": {"thread_id": review.thread_id}}
    graph  = build_director_graph(interrupt_for_human=True)

    try:
        snapshot = graph.get_state(config)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Thread not found: {exc}")

    if not snapshot or not snapshot.next:
        raise HTTPException(status_code=400, detail="Thread is not awaiting review.")

    paused_at = snapshot.next[0]
    print(f"\n[API] Human reviewed '{paused_at}': approved={review.approved}")

    graph.update_state(config, {
        "human_approved": review.approved,
        "human_feedback": review.feedback or "",
    })

    try:
        final_state = graph.invoke(None, config=config)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # Paused again at next human gate?
    next_pause = _interrupted_node(graph, config)
    if next_pause:
        state = graph.get_state(config).values
        print(f"[API] ⏸  Paused again before '{next_pause}'")
        print(f"[API]    Reason: {state.get('director_reasoning')}")
        print(f"[API]    Thread: {review.thread_id}  → POST /director/resume to continue")
        return _build_output(state, awaiting=True, current_node=next_pause, thread_id=review.thread_id)

    return _build_output(final_state, thread_id=review.thread_id)


@router.get("/status/{thread_id}", response_model=CAPADirectorOutput)
async def get_status(thread_id: str):
    """Poll current state of any analysis, including director_reasoning."""
    config = {"configurable": {"thread_id": thread_id}}
    graph  = build_director_graph(interrupt_for_human=True)

    try:
        snapshot = graph.get_state(config)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    if not snapshot:
        raise HTTPException(status_code=404, detail="Thread not found.")

    state     = snapshot.values
    paused_at = snapshot.next[0] if snapshot.next else None
    return _build_output(state, awaiting=bool(paused_at), current_node=paused_at)


@router.get("/health")
def health():
    return {"status": "online", "orchestrator": "CAPA Director O1 (True Director)", "version": "3.0"}