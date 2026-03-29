"""
Live integration tests for the rewritten loop control agent.

Run from workspace root:
    python Agents/loop_control/live_tests.py

Tests
-----
TC1  Original failing example (operator training gap, confidence=0.89)
     Expected: STOP_ROOT_FOUND  -- training gap is systemic (depth=3)

TC2  Shallow local symptom (inlet temperature dropped to 52 C)
     Expected: LOOP  -- local physical condition, depth=1

TC3  Clear process-design / validation root cause
     Expected: STOP_ROOT_FOUND

TC4  Max loops reached with circular, low-confidence cause
     Expected: STOP_DEGRADED
"""
import sys

from Agents.loop_control.agent import LoopControlAgent
from Agents.loop_control.state import LoopControlInput, WhyChainItem

agent = LoopControlAgent()
results: list[dict] = []


def run_test(name: str, payload: LoopControlInput, expected: str) -> None:
    print(f"\n{'='*72}")
    print(f"  {name}")
    print(f"  Cause : {payload.current_top_cause[:90]}")
    print(f"  Expect: {expected}")

    out = agent.evaluate(payload)
    decision = out.get("decision", "??")
    passed = decision == expected
    mark = "PASS" if passed else "FAIL"
    score = out.get("root_cause_score", {})
    chain = out.get("chain_health", {})

    print(f"  Result: [{mark}]  decision={decision}")
    print(f"  Scores: depth={score.get('system_depth')}, "
          f"action={score.get('actionability')}, "
          f"recurrence={score.get('recurrence_prevention')} ({score.get('recurrence_str')}), "
          f"total={score.get('total')}, confidence={out.get('loop_signals', {})}")
    print(f"  Chain : circular={chain.get('circular')}, "
          f"spec={chain.get('specificity_trend')}, conf={chain.get('confidence_trend')}")
    print(f"  Reason: {str(out.get('reasoning', ''))[:200]}")
    results.append({"name": name, "expected": expected, "got": decision, "pass": passed})


# ── TC1: Training gap — was incorrectly LOOP, should be STOP_ROOT_FOUND ──────
run_test(
    name="TC1  Operator training gap (was broken — should be STOP_ROOT_FOUND)",
    payload=LoopControlInput(
        incident_description=(
            "During film coating of Batch #FG-2245, the coating weight gain was below "
            "specification (4.2% vs target 5.8%) causing product rejection at QC. "
            "Pan speed and inlet temperature alarms were active for >30 minutes before "
            "the operator escalated."
        ),
        current_loop_count=3,
        max_loops=5,
        current_top_cause=(
            "Operator was not adequately trained on the criticality of inlet temperature "
            "and pan speed alarms and the required escalation response procedures."
        ),
        current_cause_confidence=0.89,
        full_why_chain=[
            WhyChainItem(
                loop=1,
                question="Why did coating weight gain fall below spec?",
                cause="Inlet temperature dropped below 58°C and pan speed deviated during coating run.",
                confidence=0.78,
            ),
            WhyChainItem(
                loop=2,
                question="Why did the operator not respond to the alarms?",
                cause="Operator did not recognize the alarms as requiring immediate intervention.",
                confidence=0.83,
            ),
        ],
    ),
    expected="STOP_ROOT_FOUND",
)

# ── TC2: Shallow local symptom — should loop ─────────────────────────────────
run_test(
    name="TC2  Local physical symptom (should LOOP)",
    payload=LoopControlInput(
        incident_description=(
            "Batch #FG-2245 failed coating weight spec (4.2% vs target 5.8%)."
        ),
        current_loop_count=1,
        max_loops=5,
        current_top_cause="Inlet temperature dropped to 52°C during the coating run.",
        current_cause_confidence=0.72,
        full_why_chain=[],
    ),
    expected="LOOP",
)

# ── TC3: Validated process design gap — should confirm root ──────────────────
run_test(
    name="TC3  Validation gap on process parameters (should STOP_ROOT_FOUND)",
    payload=LoopControlInput(
        incident_description=(
            "Film coating batch FG-2245 rejected for coating weight below specification."
        ),
        current_loop_count=2,
        max_loops=5,
        current_top_cause=(
            "Film coating process parameters (pan speed and inlet temperature control limits) "
            "were never validated for this specific tablet formulation and batch size, "
            "leaving no defined operational limits in the batch record or SOP."
        ),
        current_cause_confidence=0.91,
        full_why_chain=[
            WhyChainItem(
                loop=1,
                question="Why did coating weight fall below specification?",
                cause="Inlet temperature and pan speed operated outside optimal range for this formulation.",
                confidence=0.80,
            ),
        ],
    ),
    expected="STOP_ROOT_FOUND",
)

# ── TC4: Max loops — circular weak cause — should STOP_DEGRADED ──────────────
run_test(
    name="TC4  Max loops with shallow circular cause (should STOP_DEGRADED)",
    payload=LoopControlInput(
        incident_description=(
            "Batch FG-2245 rejected at QC for coating weight below specification."
        ),
        current_loop_count=5,   # at max
        max_loops=5,
        current_top_cause="The pan was running during the coating step.",
        current_cause_confidence=0.35,
        full_why_chain=[
            WhyChainItem(loop=1, question="Why?", cause="Temperature was low.", confidence=0.50),
            WhyChainItem(loop=2, question="Why?", cause="The pan was running.", confidence=0.40),
            WhyChainItem(loop=3, question="Why?", cause="Temperature was low again.", confidence=0.38),
            WhyChainItem(loop=4, question="Why?", cause="Pan speed issue observed.", confidence=0.36),
        ],
    ),
    expected="STOP_DEGRADED",
)

# ── TC5: Alarm fatigue / partial recurrence — should LOOP, not STOP_ROOT_FOUND ─
run_test(
    name="TC5  Alarm fatigue / partial prevention (should LOOP — was STOP_ROOT_FOUND)",
    payload=LoopControlInput(
        incident_description=(
            "During post-market surveillance of Film-Coated Tablets Batch B-202, multiple market "
            "complaints reported peeling of the film coating and reduced product effectiveness. "
            "Internal quality testing confirmed that 22% of tablets exhibited coating defects, and "
            "dissolution testing failed in 63% of samples, significantly exceeding specification "
            "limits. This indicates a critical failure in the coating process, potentially "
            "impacting product stability and therapeutic performance."
        ),
        current_loop_count=1,
        max_loops=6,
        current_top_cause=(
            "High production pressure and tight shift schedules cause alarm fatigue, "
            "prompting the operator to dismiss alarms to maintain throughput."
        ),
        current_cause_confidence=0.79,
        full_why_chain=[
            WhyChainItem(
                loop=1,
                question=(
                    "Why did the operator dismiss the inlet temperature and pan speed alarms "
                    "without taking corrective action or documenting the deviation?"
                ),
                cause=(
                    "High production pressure and tight shift schedules cause alarm fatigue, "
                    "prompting the operator to dismiss alarms to maintain throughput."
                ),
                confidence=0.79,
            ),
        ],
    ),
    expected="LOOP",
)

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'='*72}")
passed = sum(1 for r in results if r["pass"])
total = len(results)
print(f"Summary: {passed}/{total} tests passed\n")
for r in results:
    mark = "✓" if r["pass"] else "✗"
    print(f"  {mark}  {r['name'][:60]}")
    if not r["pass"]:
        print(f"       expected={r['expected']}, got={r['got']}")

sys.exit(0 if passed == total else 1)
