"""Batch evaluator for Loop Control agent with multiple test inputs.

Usage examples:
- Live LLM-backed evaluation:
  python -m Agents.loop_control.evaluate_loop_control --runs 1

- Deterministic fallback evaluation (no LLM dependency):
  python -m Agents.loop_control.evaluate_loop_control --force-fallback --runs 2
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from Agents.loop_control.agent import LoopControlAgent
from Agents.loop_control.state import LoopControlInput
from Agents.loop_control import utils as loop_utils


@dataclass
class EvalCase:
    case_id: str
    title: str
    payload: LoopControlInput
    expected_decisions: set[str]
    min_system_depth: Optional[int] = None
    max_system_depth: Optional[int] = None


@dataclass
class CaseRunResult:
    run_index: int
    decision: str
    system_depth: int
    total_score: int
    passed: bool
    errors: list[str]
    output: dict[str, Any]


def _make_chain(*causes: tuple[int, str, str, float]) -> list[dict[str, Any]]:
    chain: list[dict[str, Any]] = []
    for loop, question, cause, confidence in causes:
        chain.append(
            {
                "loop": loop,
                "question": question,
                "cause": cause,
                "confidence": confidence,
            }
        )
    return chain


def build_cases() -> list[EvalCase]:
    return [
        EvalCase(
            case_id="LC-01",
            title="System design flaw",
            payload=LoopControlInput(
                incident_description="Recurring contamination after maintenance intervention before fill restart.",
                current_loop_count=4,
                max_loops=7,
                current_top_cause="System design flaw: change-control workflow allows line restart without mandatory post-maintenance verification gate.",
                current_cause_confidence=0.84,
                full_why_chain=_make_chain(
                    (1, "Why contamination happened?", "Line clearance was inconsistent after intervention.", 0.69),
                    (2, "Why inconsistent?", "Verification ownership was not clearly enforced.", 0.74),
                    (3, "Why not enforced?", "Workflow design has no hard verification gate.", 0.80),
                    (4, "Why no hard gate?", "System design flaw: change-control workflow allows line restart without mandatory post-maintenance verification gate.", 0.84),
                ),
            ),
            expected_decisions={"STOP_ROOT_FOUND", "LOOP"},
            min_system_depth=3,
        ),
        EvalCase(
            case_id="LC-02",
            title="Lack of enforcement",
            payload=LoopControlInput(
                incident_description="Batch release resumed without required SOP hold-point evidence.",
                current_loop_count=3,
                max_loops=6,
                current_top_cause="SOP exists but was not followed because enforcement accountability was not defined across shifts.",
                current_cause_confidence=0.82,
                full_why_chain=_make_chain(
                    (1, "Why was hold-point missed?", "Checklist step was skipped.", 0.67),
                    (2, "Why skipped?", "No one verified SOP adherence during handover.", 0.75),
                    (3, "Why no verification?", "SOP exists but was not followed because enforcement accountability was not defined across shifts.", 0.82),
                ),
            ),
            expected_decisions={"STOP_ROOT_FOUND", "LOOP"},
            min_system_depth=3,
        ),
        EvalCase(
            case_id="LC-03",
            title="Tooling gap",
            payload=LoopControlInput(
                incident_description="Deviation closure occurred without required evidence attachments.",
                current_loop_count=3,
                max_loops=6,
                current_top_cause="Tooling gap: QMS has no automated block for deviation closure when evidence fields are incomplete.",
                current_cause_confidence=0.86,
                full_why_chain=_make_chain(
                    (1, "Why incomplete closure?", "Reviewer accepted partial data.", 0.64),
                    (2, "Why accepted partial data?", "System did not enforce mandatory fields.", 0.76),
                    (3, "Why no enforcement?", "Tooling gap: QMS has no automated block for deviation closure when evidence fields are incomplete.", 0.86),
                ),
            ),
            expected_decisions={"STOP_ROOT_FOUND", "LOOP"},
            min_system_depth=3,
        ),
        EvalCase(
            case_id="LC-04",
            title="Organizational ownership gap",
            payload=LoopControlInput(
                incident_description="Escalations on critical alarms were delayed during weekend shifts.",
                current_loop_count=4,
                max_loops=7,
                current_top_cause="Organizational issue: escalation ownership is split across QA and Production with no single accountable owner.",
                current_cause_confidence=0.79,
                full_why_chain=_make_chain(
                    (1, "Why delay occurred?", "Alarm was acknowledged but not escalated.", 0.65),
                    (2, "Why not escalated?", "Shift expected another team to act.", 0.72),
                    (3, "Why ambiguity?", "Escalation matrix had overlapping responsibilities.", 0.75),
                    (4, "Why overlapping?", "Organizational issue: escalation ownership is split across QA and Production with no single accountable owner.", 0.79),
                ),
            ),
            expected_decisions={"STOP_ROOT_FOUND", "LOOP"},
            min_system_depth=3,
        ),
        EvalCase(
            case_id="LC-05",
            title="Training gap",
            payload=LoopControlInput(
                incident_description="Operators skipped revised contamination-control steps after SOP update.",
                current_loop_count=3,
                max_loops=6,
                current_top_cause="Training gap: role-based requalification was not triggered after SOP revision.",
                current_cause_confidence=0.83,
                full_why_chain=_make_chain(
                    (1, "Why steps skipped?", "Team followed older method.", 0.66),
                    (2, "Why older method?", "Operators were not requalified on new SOP.", 0.77),
                    (3, "Why no requalification?", "Training gap: role-based requalification was not triggered after SOP revision.", 0.83),
                ),
            ),
            expected_decisions={"STOP_ROOT_FOUND", "LOOP"},
            min_system_depth=3,
        ),
        EvalCase(
            case_id="LC-06",
            title="Resource constraint",
            payload=LoopControlInput(
                incident_description="Mandatory in-process checks were frequently deferred in peak demand weeks.",
                current_loop_count=4,
                max_loops=7,
                current_top_cause="Resource constraint: chronic understaffing removed available time for mandatory verification checks.",
                current_cause_confidence=0.78,
                full_why_chain=_make_chain(
                    (1, "Why checks deferred?", "Tasks queued near shift-end.", 0.63),
                    (2, "Why queued?", "Single operator handled too many workcenters.", 0.70),
                    (3, "Why one operator?", "Backfill plans were not approved.", 0.73),
                    (4, "Why no backfill?", "Resource constraint: chronic understaffing removed available time for mandatory verification checks.", 0.78),
                ),
            ),
            expected_decisions={"STOP_ROOT_FOUND", "LOOP"},
            min_system_depth=3,
        ),
        EvalCase(
            case_id="LC-07",
            title="Degraded circular chain",
            payload=LoopControlInput(
                incident_description="Investigative chain keeps repeating non-specific reasons without narrowing root mechanism.",
                current_loop_count=4,
                max_loops=6,
                current_top_cause="Issue happened due to general inconsistency and recurring confusion.",
                current_cause_confidence=0.56,
                full_why_chain=_make_chain(
                    (1, "Why issue?", "Pump temperature drifted by 2.3 C post-maintenance.", 0.69),
                    (2, "Why drift?", "Controls were not clear.", 0.61),
                    (3, "Why not controlled?", "General process issue happened.", 0.58),
                    (4, "Why general issue?", "Issue happened due to general inconsistency and recurring confusion.", 0.56),
                ),
            ),
            expected_decisions={"STOP_DEGRADED"},
        ),
        EvalCase(
            case_id="LC-08",
            title="Local symptom only",
            payload=LoopControlInput(
                incident_description="Seal leaks increased during second shift startup window.",
                current_loop_count=3,
                max_loops=6,
                current_top_cause="Sealing jaw temperature was slightly low during startup.",
                current_cause_confidence=0.74,
                full_why_chain=_make_chain(
                    (1, "Why leak?", "Seal integrity dropped in startup lots.", 0.68),
                    (2, "Why integrity drop?", "Heat profile varied around startup.", 0.72),
                    (3, "Why heat profile varied?", "Sealing jaw temperature was slightly low during startup.", 0.74),
                ),
            ),
            expected_decisions={"LOOP", "STOP_DEGRADED"},
            max_system_depth=2,
        ),
        EvalCase(
            case_id="LC-09",
            title="Max loops exhausted",
            payload=LoopControlInput(
                incident_description="Repeat deviations continue despite multiple why loops and no stable systemic explanation.",
                current_loop_count=6,
                max_loops=6,
                current_top_cause="The issue may be due to some general inconsistency in operations.",
                current_cause_confidence=0.52,
                full_why_chain=_make_chain(
                    (1, "Why deviation?", "Variation observed in operations.", 0.61),
                    (2, "Why variation?", "Some inconsistency across shifts.", 0.58),
                    (3, "Why inconsistency?", "General operational issue.", 0.55),
                    (4, "Why general issue?", "Some inconsistency across teams.", 0.54),
                    (5, "Why across teams?", "General issue persisted.", 0.53),
                    (6, "Why persisted?", "The issue may be due to some general inconsistency in operations.", 0.52),
                ),
            ),
            expected_decisions={"STOP_DEGRADED"},
            max_system_depth=2,
        ),
    ]


def validate_output(case: EvalCase, output: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    decision = str(output.get("decision", ""))
    if decision not in case.expected_decisions:
        errors.append(f"decision={decision} not in expected={sorted(case.expected_decisions)}")

    score = output.get("root_cause_score") or {}
    system_depth = score.get("system_depth")

    if not isinstance(system_depth, int):
        errors.append(f"system_depth is not int: {system_depth!r}")
    else:
        if case.min_system_depth is not None and system_depth < case.min_system_depth:
            errors.append(
                f"system_depth={system_depth} is below min_system_depth={case.min_system_depth}"
            )
        if case.max_system_depth is not None and system_depth > case.max_system_depth:
            errors.append(
                f"system_depth={system_depth} is above max_system_depth={case.max_system_depth}"
            )

    next_step = output.get("next_step")
    if decision == "LOOP" and not isinstance(next_step, dict):
        errors.append("decision=LOOP but next_step is missing")
    if decision in {"STOP_ROOT_FOUND", "STOP_DEGRADED"} and next_step is not None:
        errors.append("stop decision should have next_step=None")

    return errors


def evaluate_cases(cases: list[EvalCase], runs: int, force_fallback: bool) -> dict[str, Any]:
    agent = LoopControlAgent()
    results: dict[str, Any] = {
        "runs_per_case": runs,
        "force_fallback": force_fallback,
        "cases": [],
        "summary": {},
    }

    original_assess = loop_utils._assess_root_cause
    if force_fallback:
        def _raise_forced_fallback(_payload):
            raise RuntimeError("forced fallback mode")

        loop_utils._assess_root_cause = _raise_forced_fallback

    total_runs = 0
    total_passed = 0

    try:
        for case in cases:
            case_runs: list[CaseRunResult] = []

            for run_index in range(1, runs + 1):
                output = agent.evaluate(case.payload)
                run_errors = validate_output(case, output)
                decision = str(output.get("decision", ""))
                score = output.get("root_cause_score") or {}
                system_depth = int(score.get("system_depth", -1))
                total_score = int(score.get("total", -1))
                passed = len(run_errors) == 0

                case_runs.append(
                    CaseRunResult(
                        run_index=run_index,
                        decision=decision,
                        system_depth=system_depth,
                        total_score=total_score,
                        passed=passed,
                        errors=run_errors,
                        output=output,
                    )
                )

                total_runs += 1
                if passed:
                    total_passed += 1

            case_pass_rate = sum(1 for item in case_runs if item.passed) / len(case_runs)
            decision_hist: dict[str, int] = {}
            for item in case_runs:
                decision_hist[item.decision] = decision_hist.get(item.decision, 0) + 1

            results["cases"].append(
                {
                    "case_id": case.case_id,
                    "title": case.title,
                    "expected_decisions": sorted(case.expected_decisions),
                    "min_system_depth": case.min_system_depth,
                    "max_system_depth": case.max_system_depth,
                    "pass_rate": round(case_pass_rate, 3),
                    "decision_histogram": decision_hist,
                    "runs": [
                        {
                            "run_index": item.run_index,
                            "decision": item.decision,
                            "system_depth": item.system_depth,
                            "total_score": item.total_score,
                            "passed": item.passed,
                            "errors": item.errors,
                            "reasoning": item.output.get("reasoning"),
                        }
                        for item in case_runs
                    ],
                }
            )
    finally:
        loop_utils._assess_root_cause = original_assess

    overall_pass_rate = (total_passed / total_runs) if total_runs else 0.0
    results["summary"] = {
        "total_cases": len(cases),
        "total_runs": total_runs,
        "passed_runs": total_passed,
        "failed_runs": total_runs - total_passed,
        "overall_pass_rate": round(overall_pass_rate, 3),
    }
    return results


def print_human_summary(report: dict[str, Any]) -> None:
    summary = report["summary"]
    print("=" * 88)
    print("LOOP CONTROL MULTI-INPUT EVALUATION")
    print("=" * 88)
    print(f"runs_per_case     : {report['runs_per_case']}")
    print(f"force_fallback    : {report['force_fallback']}")
    print(f"total_cases       : {summary['total_cases']}")
    print(f"total_runs        : {summary['total_runs']}")
    print(f"passed_runs       : {summary['passed_runs']}")
    print(f"failed_runs       : {summary['failed_runs']}")
    print(f"overall_pass_rate : {summary['overall_pass_rate']}")
    print("-" * 88)

    for case in report["cases"]:
        print(f"{case['case_id']} | {case['title']}")
        print(f"  expected_decisions : {case['expected_decisions']}")
        print(f"  decision_histogram : {case['decision_histogram']}")
        print(f"  pass_rate          : {case['pass_rate']}")
        run_failures = [r for r in case["runs"] if not r["passed"]]
        if run_failures:
            for failure in run_failures:
                print(
                    f"  run={failure['run_index']} FAILED | decision={failure['decision']} | "
                    f"system_depth={failure['system_depth']} | errors={failure['errors']}"
                )
        else:
            print("  all runs passed")
        print("-" * 88)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Loop Control agent with multiple curated inputs")
    parser.add_argument("--runs", type=int, default=1, help="How many times to run each case")
    parser.add_argument(
        "--force-fallback",
        action="store_true",
        help="Force deterministic fallback scoring by bypassing LLM assessment",
    )
    parser.add_argument(
        "--report-path",
        default="Agents/loop_control/loop_control_eval_report.json",
        help="Where to write JSON report",
    )
    args = parser.parse_args()

    runs = max(1, args.runs)
    cases = build_cases()
    report = evaluate_cases(cases=cases, runs=runs, force_fallback=args.force_fallback)

    print_human_summary(report)

    report_path = Path(args.report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Report written to: {report_path}")

    failed_runs = report["summary"].get("failed_runs", 0)
    return 0 if failed_runs == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
