"use client";

import { useState, useCallback } from "react";
import RCAIntakeForm from "@/components/RCAIntakeForm";
import RCAStatusPanel from "@/components/RCAStatusPanel";
import FishboneDecidePanel from "@/components/FishboneDecidePanel";
import CategorySelectPanel from "@/components/CategorySelectPanel";
import WhyReviewPanel from "@/components/WhyReviewPanel";
import WhyConcludedPanel from "@/components/WhyConcludedPanel";
import ActionPlanPanel from "@/components/ActionPlanPanel";

import {
  startRCA,
  selectCategory,
  proceedActionPlan,
  submitFishboneDecisions,
  submitWhyHumanReview,
  fetchRcaStatus,
} from "@/lib/api/rca";
import type {
  RCAResponse,
  RCAStartInput,
  FishboneCauseDecision,
  WhyHumanReviewInput,
} from "@/lib/api/rca";

type UIStep =
  | "intake"
  | "fishbone_internal_hitl"   // waiting for user to submit /fishbone-v3/decide
  | "category_select"          // HITL #2 — pick fishbone category
  | "why_internal_hitl"        // waiting for user to submit /why-analysis-v3/human-review
  | "why_concluded"            // why ended automatically (low confidence / max depth)
  | "action_plan_confirm"      // HITL #3 — confirm action plan
  | "completed";

export default function Page() {
  const [step, setStep] = useState<UIStep>("intake");
  const [rcaResponse, setRcaResponse] = useState<RCAResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionPlanConfirmed, setActionPlanConfirmed] = useState<boolean | undefined>(undefined);

  const clearError = () => setError(null);

  // ── Derive state ─────────────────────────────────────────────────────────

  // Fishbone high-confidence causes from the fishbone_output
  const fishboneCauses = extractHighConfidenceCauses(rcaResponse?.fishbone_output);

  // Why output (may be updated by /why-analysis-v3/human-review responses)
  const [localWhyOutput, setLocalWhyOutput] = useState<Record<string, unknown> | null>(null);
  const effectiveWhyOutput = localWhyOutput ?? (rcaResponse?.why_output as Record<string, unknown> | null) ?? null;

  // ── Step: HITL #1 — Start RCA ────────────────────────────────────────────

  async function handleStart(payload: RCAStartInput) {
    clearError();
    setLoading(true);
    try {
      const res = await startRCA(payload);
      setRcaResponse(res);

      if (res.phase === "fishbone_running") {
        // Check fishbone status directly: only show HITL panel when backend is waiting for human
        const fo = res.fishbone_output as Record<string, unknown> | null;
        const fishboneStatus = typeof fo?.status === "string" ? fo.status : "";
        if (fishboneStatus === "WAIT_FOR_HUMAN") {
          setStep("fishbone_internal_hitl");
        } else {
          // No high-confidence causes (fishbone completed automatically) → go straight to category select
          setStep("category_select");
        }
      } else if (res.phase === "why_running") {
        // Why Analysis started — check if it needs immediate human review
        // ai_flagged means zero-evidence ran; the analysis is concluded even if
        // awaiting_human_review is stale-true from a prior graph checkpoint.
        const whyOut = res.why_output as Record<string, unknown> | null;
        if (whyOut?.awaiting_human_review && !whyOut?.ai_flagged) {
          setStep("why_internal_hitl");
        } else {
          setLocalWhyOutput(whyOut);
          setStep("why_concluded");
        }
      } else if (res.phase === "error") {
        setError(res.error ?? "An error occurred.");
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  // ── Step: Fishbone internal HITL — submit decisions to /fishbone-v3/decide ─

  const handleFishboneDecisions = useCallback(
    async (decisions: FishboneCauseDecision[]) => {
      if (!rcaResponse) return;
      clearError();
      setLoading(true);
      try {
        // Submit to the child orchestrator directly
        await submitFishboneDecisions(rcaResponse.complaint_id, decisions);

        // Refresh RCA state so we get updated fishbone_output + available_categories
        const refreshed = await fetchRcaStatus(rcaResponse.complaint_id);
        setRcaResponse(refreshed);
        setStep("category_select");
      } catch (e) {
        setError(String(e));
      } finally {
        setLoading(false);
      }
    },
    [rcaResponse],
  );

  // ── Step: HITL #2 — Select category ──────────────────────────────────────

  async function handleCategorySelect(category: string) {
    if (!rcaResponse) return;
    clearError();
    setLoading(true);
    try {
      const res = await selectCategory(rcaResponse.complaint_id, category);
      setRcaResponse(res);

      const whyOut = res.why_output as Record<string, unknown> | null;
      if (whyOut?.awaiting_human_review && !whyOut?.ai_flagged) {
        setStep("why_internal_hitl");
      } else {
        setLocalWhyOutput(whyOut);
        setStep("why_concluded");
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  // ── Step: Why internal HITL — submit cause selection ─────────────────────

  const handleWhyReview = useCallback(
    async (input: WhyHumanReviewInput) => {
      if (!rcaResponse) return;
      clearError();
      setLoading(true);
      try {
        const whyResult = await submitWhyHumanReview(input);
        setLocalWhyOutput(whyResult);

        // Check if Why is still awaiting more review.
        // ai_flagged means zero-evidence ran and the analysis has concluded.
        if (whyResult.awaiting_human_review && !whyResult.ai_flagged) {
          setStep("why_internal_hitl"); // another iteration
        } else {
          // Analysis concluded (ai_flagged, max-depth, or auto-complete)
          setStep("why_concluded");
        }
      } catch (e) {
        setError(String(e));
      } finally {
        setLoading(false);
      }
    },
    [rcaResponse],
  );

  // ── Step: HITL #3 — Confirm action plan ──────────────────────────────────

  async function handleActionPlanConfirm(confirmed: boolean) {
    if (!rcaResponse) return;
    clearError();
    setLoading(true);
    try {
      const res = await proceedActionPlan(rcaResponse.complaint_id, confirmed);
      setRcaResponse(res);
      setActionPlanConfirmed(confirmed);
      if (confirmed && res.phase === "completed") {
        setStep("completed");
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  function handleStartNew() {
    setStep("intake");
    setRcaResponse(null);
    setLocalWhyOutput(null);
    setActionPlanConfirmed(undefined);
    setError(null);
  }

  // ── Step: Why concluded — user acknowledges and continues ────────────────
  // handled inline via onContinue={() => setStep("action_plan_confirm")}

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <main className="min-h-screen bg-background">
      <div className="max-w-3xl mx-auto px-4 py-10 space-y-6">

        {/* Status panel (shown once a session exists) */}
        {rcaResponse && (
          <RCAStatusPanel response={rcaResponse} loading={loading} />
        )}

        {/* Loading progress banner */}
        {loading && <AnalysisProgressBanner step={step} />}

        {/* Global error */}
        {error && (
          <div className="rounded-xl border border-danger/30 bg-danger/8 px-4 py-3 text-sm text-danger flex items-start justify-between gap-3">
            <span>{error}</span>
            <button
              type="button"
              onClick={clearError}
              className="shrink-0 text-danger/60 hover:text-danger transition-colors text-lg leading-none"
            >
              ✕
            </button>
          </div>
        )}

        {/* Step panels */}
        {step === "intake" && (
          <RCAIntakeForm onSubmit={handleStart} loading={loading} />
        )}

        {step === "fishbone_internal_hitl" && fishboneCauses.length > 0 && (
          <FishboneDecidePanel
            causes={fishboneCauses}
            onSubmit={handleFishboneDecisions}
            loading={loading}
          />
        )}

        {step === "category_select" && rcaResponse && (
          <CategorySelectPanel
            categories={rcaResponse.available_categories}
            fishboneOutput={rcaResponse.fishbone_output}
            onSelect={handleCategorySelect}
            loading={loading}
          />
        )}

        {step === "why_internal_hitl" && effectiveWhyOutput && rcaResponse?.why_session_id && (
          <WhyReviewPanel
            sessionId={rcaResponse.why_session_id}
            whyOutput={effectiveWhyOutput}
            onSubmit={handleWhyReview}
            loading={loading}
          />
        )}

        {step === "why_concluded" && effectiveWhyOutput && (
          <WhyConcludedPanel
            whyOutput={effectiveWhyOutput}
            onContinue={() => setStep("action_plan_confirm")}
          />
        )}

        {(step === "action_plan_confirm" || step === "completed") && rcaResponse && (
          <ActionPlanPanel
            response={rcaResponse}
            onConfirm={() => handleActionPlanConfirm(true)}
            onReject={() => handleActionPlanConfirm(false)}
            onStartNew={handleStartNew}
            loading={loading}
            confirmed={actionPlanConfirmed}
          />
        )}
      </div>
    </main>
  );
}

/* ── Helpers ─────────────────────────────────────────────────────────── */

/** Safely extract a string value from a Record<string, unknown> by trying multiple keys. */
function safeField(obj: Record<string, unknown>, ...keys: string[]): string {
  for (const k of keys) {
    const v = obj[k];
    if (typeof v === "string" && v) return v;
  }
  return "";
}

function extractHighConfidenceCauses(
  fishboneOutput: Record<string, unknown> | null | undefined,
): Array<{
  cause_id: string;
  cause_text: string;
  category?: string;
  validation_confidence?: number;
  validation_status?: string;
}> {
  if (!fishboneOutput) return [];

  // Only use high_confidence_causes — falling back to all_categorized_causes would show
  // all causes even when fishbone completed without HITL, causing /fishbone-v3/decide 404s.
  for (const key of ["high_confidence_causes", "causes_for_human_review"]) {
    const list = fishboneOutput[key];
    if (!Array.isArray(list) || list.length === 0) continue;

    return list
      .filter((c): c is Record<string, unknown> => c !== null && typeof c === "object")
      .map((c) => ({
        cause_id: safeField(c, "cause_id", "id"),
        cause_text: safeField(c, "cause_text", "text", "cause"),
        category: safeField(c, "category") || undefined,
        validation_confidence:
          typeof c.validation_confidence === "number" ? c.validation_confidence : undefined,
        validation_status: safeField(c, "validation_status") || undefined,
      }))
      .filter((c) => c.cause_id && c.cause_text);
  }

  return [];
}

/* ── Loading progress banner ─────────────────────────────────────────── */

const PROGRESS_STEPS: Record<UIStep, { label: string; steps: string[] }> = {
  intake: {
    label: "Starting analysis\u2026",
    steps: ["Generating Why question\u2026", "Finding potential causes\u2026", "Validating against evidence\u2026"],
  },
  fishbone_internal_hitl: {
    label: "Submitting decisions\u2026",
    steps: ["Processing cause decisions\u2026", "Updating fishbone output\u2026", "Preparing categories\u2026"],
  },
  category_select: {
    label: "Starting Why Analysis\u2026",
    steps: ["Seeding Why Analysis\u2026", "Generating Why question\u2026", "Validating causes\u2026"],
  },
  why_internal_hitl: {
    label: "Processing selection\u2026",
    steps: ["Recording decision\u2026", "Generating next question\u2026", "Validating causes\u2026"],
  },
  why_concluded: {
    label: "Finalising analysis\u2026",
    steps: ["Selecting best available cause\u2026", "Closing Why iteration\u2026"],
  },
  action_plan_confirm: {
    label: "Confirming\u2026",
    steps: ["Recording approval\u2026", "Preparing action plan\u2026", "Finalising RCA\u2026"],
  },
  completed: {
    label: "Completing\u2026",
    steps: ["Finalising\u2026"],
  },
};

function AnalysisProgressBanner({ step }: Readonly<{ step: UIStep }>) {
  const { label, steps } = PROGRESS_STEPS[step] ?? PROGRESS_STEPS.intake;
  return (
    <div className="rounded-xl border border-accent-2/30 bg-accent-2/5 px-5 py-4 space-y-3">
      <div className="flex items-center gap-3">
        <span className="inline-block w-4 h-4 rounded-full border-2 border-accent-2 border-t-transparent animate-spin shrink-0" />
        <p className="text-sm font-semibold text-accent-2">{label}</p>
      </div>
      <div className="space-y-1.5">
        {steps.map((s) => (
          <div key={s} className="flex items-center gap-2 text-xs text-muted">
            <span className="inline-block w-2.5 h-2.5 rounded-full border border-accent-2/50 border-t-transparent animate-spin shrink-0" />
            {s}
          </div>
        ))}
      </div>
    </div>
  );
}
