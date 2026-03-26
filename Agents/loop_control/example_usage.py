"""
Example usage for Loop Control agent.

Includes one test input and prints strict JSON output.
"""

import json

from Agents.loop_control.agent import LoopControlAgent
from Agents.loop_control.state import LoopControlInput


def run_example():
    payload = LoopControlInput(
        incident_description="Recurring contamination in final rinse water line during batch closeout.",
        current_loop_count=3,
        max_loops=5,
        current_top_cause=(
            "No formal change-control trigger exists to re-qualify sanitation SOP training "
            "after process design updates"
        ),
        current_cause_confidence=0.81,
        full_why_chain=[
            {
                "loop": 1,
                "question": "Why did contamination occur?",
                "cause": "Rinse line cleaning was inconsistent",
                "confidence": 0.72,
            },
            {
                "loop": 2,
                "question": "Why was cleaning inconsistent?",
                "cause": "Operators followed outdated sanitation instructions",
                "confidence": 0.76,
            },
            {
                "loop": 3,
                "question": "Why were instructions outdated?",
                "cause": (
                    "No formal change-control trigger exists to re-qualify sanitation SOP training "
                    "after process design updates"
                ),
                "confidence": 0.81,
            },
        ],
    )

    agent = LoopControlAgent()
    output = agent.evaluate(payload)

    print("INPUT:")
    print(json.dumps(payload.model_dump(), indent=2))
    print("\nOUTPUT:")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    run_example()
