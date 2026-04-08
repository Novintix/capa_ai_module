"""
Stability test: run the same input 10 times and report score distributions.
Diagnoses non-determinism in borderline cases.

Run:
    python -m Agents.loop_control.stability_test
"""
import sys
from collections import Counter

from Agents.loop_control.agent import LoopControlAgent
from Agents.loop_control.state import LoopControlInput, WhyChainItem

agent = LoopControlAgent()
RUNS = 10

CASES = [
    {
        "name": "Short validation-gap cause (user's Case B)",
        "expected": "STOP_ROOT_FOUND",
        "payload": LoopControlInput(
            incident_description=(
                "Film-coated tablets from Batch B-202 were rejected during QC. "
                "22% exhibited visible coating defects (peeling, uneven coverage) and "
                "63% failed dissolution testing, exceeding specification limits. "
                "Batch was flagged during post-market surveillance and confirmed by in-house testing."
            ),
            current_loop_count=1,
            max_loops=6,
            current_top_cause=(
                "The film coating process parameters (inlet temperature range, spray rate, "
                "and pan speed limits) were never formally validated for this specific tablet."
            ),
            current_cause_confidence=0.88,
            full_why_chain=[
                WhyChainItem(
                    loop=1,
                    question="Why did 22% of tablets exhibit coating defects and 63% fail dissolution testing in Batch B-202?",
                    cause=(
                        "The film coating process parameters (inlet temperature range, spray rate, "
                        "and pan speed limits) were never formally validated for this specific tablet."
                    ),
                    confidence=0.88,
                ),
            ],
        ),
    },
    {
        "name": "Alarm fatigue (should stay LOOP every time)",
        "expected": "LOOP",
        "payload": LoopControlInput(
            incident_description=(
                "During post-market surveillance of Film-Coated Tablets Batch B-202, multiple market "
                "complaints reported peeling of the film coating and reduced product effectiveness. "
                "Internal quality testing confirmed that 22% of tablets exhibited coating defects, "
                "and dissolution testing failed in 63% of samples."
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
                    question="Why did the operator dismiss alarms without corrective action?",
                    cause=(
                        "High production pressure and tight shift schedules cause alarm fatigue, "
                        "prompting the operator to dismiss alarms to maintain throughput."
                    ),
                    confidence=0.79,
                ),
            ],
        ),
    },
]


overall_pass = True

for case in CASES:
    name = case["name"]
    expected = case["expected"]
    payload = case["payload"]

    decisions = []
    score_totals = []
    recurrence_labels = []
    llm_verdicts = []

    print(f"\n{'='*72}")
    print(f"  {name}")
    print(f"  Expected every run: {expected}  ({RUNS} runs)")
    print()

    for i in range(RUNS):
        out = agent.evaluate(payload)
        decision = out.get("decision", "??")
        score = out.get("root_cause_score", {})
        total = score.get("total", "?")
        rec = score.get("recurrence_str", "?")
        # loop_signals is not in LoopControlOutput — read from reasoning text as proxy
        decisions.append(decision)
        score_totals.append(total)
        recurrence_labels.append(rec)
        mark = "✓" if decision == expected else "✗"
        print(f"  Run {i+1:2d}: {mark} decision={decision:<18} total={total}  recurrence={rec}")

    decision_counts = Counter(decisions)
    passed = all(d == expected for d in decisions)
    overall_pass = overall_pass and passed

    print()
    print(f"  Decision distribution : {dict(decision_counts)}")
    print(f"  Score totals          : {Counter(score_totals)}")
    print(f"  Recurrence labels     : {Counter(recurrence_labels)}")
    print(f"  Stability             : {'STABLE ✓' if passed else 'UNSTABLE ✗  — flipping between decisions'}")


print(f"\n{'='*72}")
print(f"Overall: {'ALL STABLE ✓' if overall_pass else 'UNSTABLE ✗ — see details above'}")
sys.exit(0 if overall_pass else 1)
