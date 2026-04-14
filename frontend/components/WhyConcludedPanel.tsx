"use client";

import { useState } from "react";

/* -- Types ---------------------------------------------------------------- */

interface LastCause {
  cause_id: string;
  cause_text: string;
  validation_confidence?: number;
  evidence_match_status?: string;
  severity?: string;
  reason?: string;
  selection_path?: string;
}

interface WhyConcludedPanelProps {
  readonly whyOutput: Record<string, unknown>;
  readonly onContinue: () => void;
}

/* -- Helpers -------------------------------------------------------------- */

function sfObj(obj: Record<string, unknown>, ...keys: string[]): string {
  for (const k of keys) {
    const v = obj[k];
    if (typeof v === "string" && v) return v;
  }
  return "";
}

function confidenceCls(conf: number): string {
  if (conf >= 0.9) return "bg-accent-2";
  if (conf >= 0.7) return "bg-yellow-400";
  return "bg-danger";
}

function extractRootCause(wo: Record<string, unknown>): LastCause | null {
  const rc = wo.root_cause;
  if (rc && typeof rc === "object") {
    const r = rc as Record<string, unknown>;
    const text = sfObj(r, "cause_text", "text");
    if (!text) return null;
    return {
      cause_id: sfObj(r, "cause_id", "id"),
      cause_text: text,
      validation_confidence:
        typeof r.validation_confidence === "number" ? r.validation_confidence : undefined,
      evidence_match_status:
        typeof r.evidence_match_status === "string" ? r.evidence_match_status : undefined,
      severity: sfObj(r, "severity") || undefined,
      reason: sfObj(r, "reason") || undefined,
      selection_path: sfObj(r, "selection_path") || undefined,
    };
  }
  return null;
}

function extractLastCauses(wo: Record<string, unknown>): LastCause[] {
  // Try to grab last iteration_outputs validated_causes for context
  const iters = wo.iteration_outputs;
  const list = Array.isArray(iters) && iters.length > 0
    ? (iters[iters.length - 1] as Record<string, unknown>)?.validated_causes
    : wo.validated_causes;

  if (!Array.isArray(list)) return [];
  return list
    .filter((c): c is Record<string, unknown> => c !== null && typeof c === "object")
    .map((c) => ({
      cause_id: sfObj(c, "cause_id", "id"),
      cause_text: sfObj(c, "cause_text", "text", "cause"),
      validation_confidence:
        typeof c.validation_confidence === "number" ? c.validation_confidence : undefined,
      evidence_match_status:
        typeof c.evidence_match_status === "string" ? c.evidence_match_status : undefined,
    }))
    .filter((c) => c.cause_id && c.cause_text);
}

type ClosureReason = "ai_flagged" | "max_depth" | "no_qualified" | "completed_auto";

function detectClosureReason(wo: Record<string, unknown>): ClosureReason {
  const status = sfObj(wo, "status");
  if (status === "ai_flagged") return "ai_flagged";

  const stopping = sfObj(wo, "stopping_reason").toLowerCase();
  if (stopping.includes("max") || stopping.includes("depth") || stopping.includes("iteration")) {
    return "max_depth";
  }
  if (stopping.includes("no qualified") || stopping.includes("no valid") || stopping.includes("confidence")) {
    return "no_qualified";
  }

  // Infer: check if last-iteration causes all had < 90% confidence
  const causes = extractLastCauses(wo);
  const anyQualified = causes.some(
    (c) =>
      (c.validation_confidence ?? 0) >= 0.9 &&
      c.evidence_match_status?.toLowerCase() === "matched",
  );
  if (!anyQualified && causes.length > 0) return "no_qualified";

  return "completed_auto";
}

/* -- Banner sub-components ----------------------------------------------- */

function AiFlaggedBanner() {
  return (
    <div className="rounded-xl border border-yellow-400/50 bg-yellow-50/60 px-5 py-4 space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-xl">&#x26A0;&#xFE0F;</span>
        <p className="text-sm font-bold text-yellow-700">
          AI Auto-Selected Root Cause &#8212; Low Confidence
        </p>
      </div>
      <p className="text-xs text-yellow-700/80">
        All validated causes were <strong>below the 90% confidence threshold</strong> or lacked evidence
        matching. The AI automatically selected the most critical cause based on severity score,
        failure mode analysis, and safety risk assessment.
      </p>
      <p className="text-xs text-yellow-700 font-semibold">
        &#9888; Manual investigation is recommended to verify this root cause before proceeding.
      </p>
    </div>
  );
}

function MaxDepthBanner({ depth }: Readonly<{ depth?: number }>) {
  return (
    <div className="rounded-xl border border-accent-2/30 bg-accent-2/5 px-5 py-4 space-y-1.5">
      <div className="flex items-center gap-2">
        <span className="text-xl">&#x1F9E0;</span>
        <p className="text-sm font-bold text-accent-2">
          Maximum Analysis Depth Reached
          {depth !== undefined && (
            <span className="font-normal text-muted ml-1.5">(depth {depth})</span>
          )}
        </p>
      </div>
      <p className="text-xs text-muted">
        The Why Analysis reached its configured maximum iteration depth. The AI selected the deepest
        validated cause as the root cause.
      </p>
    </div>
  );
}

function NoQualifiedBanner({ totalCauses }: Readonly<{ totalCauses: number }>) {
  return (
    <div className="rounded-xl border border-danger/30 bg-danger/5 px-5 py-4 space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-xl">&#x1F50D;</span>
        <p className="text-sm font-bold text-danger">
          No Qualified Causes Found in Final Iteration
        </p>
      </div>
      {totalCauses > 0 ? (
        <p className="text-xs text-muted">
          {totalCauses} cause{totalCauses === 1 ? " was" : "s were"} generated but{" "}
          <strong>none met the &#x2265;90% confidence + matched evidence threshold</strong>. The AI
          selected the highest-scoring available cause to avoid blocking the workflow.
        </p>
      ) : (
        <p className="text-xs text-muted">
          No causes were generated in the final iteration. The AI closed the analysis using the
          best available result from previous iterations.
        </p>
      )}
      <p className="text-xs text-danger font-semibold">
        &#9888; Review the selected root cause carefully before proceeding.
      </p>
    </div>
  );
}

/* -- Cause table ---------------------------------------------------------- */

function LastCausesTable({ causes }: Readonly<{ causes: LastCause[] }>) {
  const [open, setOpen] = useState(false);
  if (causes.length === 0) return null;

  const plural = causes.length === 1 ? "cause" : "causes";
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((s) => !s)}
        className="flex items-center gap-2 text-xs font-semibold text-muted hover:text-foreground transition-colors"
      >
        <span className={`transition-transform duration-150 ${open ? "rotate-90" : ""}`}>
          &#x25B6;
        </span>
        Final iteration {plural} ({causes.length}) &#8212; why none qualified
      </button>
      {open && (
        <div className="mt-2 space-y-2">
          {causes.map((c) => {
            const conf = c.validation_confidence ?? 0;
            const isLow = conf < 0.9;
            return (
              <div
                key={c.cause_id}
                className="rounded-lg border border-foreground/10 bg-surface-strong px-3 py-2.5"
              >
                <div className="flex items-start justify-between gap-3 mb-1.5">
                  <p className="text-xs text-foreground flex-1">{c.cause_text}</p>
                  <span
                    className={`text-xs font-mono font-bold shrink-0 ${
                      isLow ? "text-danger" : "text-accent-2"
                    }`}
                  >
                    {Math.round(conf * 100)}%
                  </span>
                </div>
                <div className="w-full h-1 rounded-full bg-foreground/10 overflow-hidden mb-1.5">
                  <div
                    className={`h-full rounded-full ${confidenceCls(conf)}`}
                    style={{ width: `${conf * 100}%` }}
                  />
                </div>
                <div className="flex gap-3 text-xs text-muted">
                  {c.evidence_match_status && (
                    <span>
                      Match:{" "}
                      <span className={c.evidence_match_status.toLowerCase() === "matched" ? "text-accent-2 font-medium" : "text-danger font-medium"}>
                        {c.evidence_match_status}
                      </span>
                    </span>
                  )}
                  {isLow && <span className="text-danger">Below 90% threshold</span>}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* -- Main component ------------------------------------------------------- */

export default function WhyConcludedPanel({
  whyOutput,
  onContinue,
}: Readonly<WhyConcludedPanelProps>) {
  const reason = detectClosureReason(whyOutput);
  const rootCause = extractRootCause(whyOutput);
  const lastCauses = extractLastCauses(whyOutput);
  const stoppingReason = sfObj(whyOutput, "stopping_reason");
  const depth =
    typeof whyOutput.analysis_depth === "number" ? whyOutput.analysis_depth : undefined;

  const qualifiedCount = lastCauses.filter(
    (c) =>
      (c.validation_confidence ?? 0) >= 0.9 &&
      c.evidence_match_status?.toLowerCase() === "matched",
  ).length;

  return (
    <div className="w-full rounded-2xl border border-foreground/10 bg-surface p-6 space-y-5">
      {/* Section label */}
      <div>
        <p className="text-xs font-mono uppercase tracking-widest text-muted mb-1">
          Why Analysis &#8212; Concluded
        </p>
        <h2 className="text-lg font-bold text-foreground">
          Analysis Closed Automatically
        </h2>
      </div>

      {/* Closure reason banner */}
      {reason === "ai_flagged" && <AiFlaggedBanner />}
      {reason === "no_qualified" && <NoQualifiedBanner totalCauses={lastCauses.length} />}
      {reason === "max_depth" && <MaxDepthBanner depth={depth} />}
      {reason === "completed_auto" && (
        <div className="rounded-xl border border-foreground/10 bg-surface-strong px-5 py-4">
          <div className="flex items-center gap-2">
            <span className="text-xl">&#x2705;</span>
            <p className="text-sm font-semibold text-foreground">
              Analysis concluded &#8212; root cause determined
            </p>
          </div>
          <p className="text-xs text-muted mt-1">
            The Why Analysis completed all iterations and determined a root cause.
          </p>
        </div>
      )}

      {/* Stopping reason (raw) */}
      {stoppingReason && (
        <p className="text-xs text-muted italic">
          Reported stopping reason: &#x201C;{stoppingReason}&#x201D;
        </p>
      )}

      {/* Stats row */}
      <div className="flex flex-wrap gap-3">
        {depth !== undefined && (
          <div className="rounded-lg bg-surface-strong border border-foreground/10 px-4 py-2 text-center">
            <p className="text-lg font-bold text-foreground">{depth}</p>
            <p className="text-xs text-muted">Analysis Depth</p>
          </div>
        )}
        <div className="rounded-lg bg-surface-strong border border-foreground/10 px-4 py-2 text-center">
          <p className="text-lg font-bold text-foreground">{lastCauses.length}</p>
          <p className="text-xs text-muted">Final Iteration Causes</p>
        </div>
        <div className="rounded-lg bg-surface-strong border border-foreground/10 px-4 py-2 text-center">
          <p className={`text-lg font-bold ${qualifiedCount === 0 ? "text-danger" : "text-accent-2"}`}>
            {qualifiedCount}
          </p>
          <p className="text-xs text-muted">Qualified (&#x2265;90%)</p>
        </div>
      </div>

      {/* AI-selected root cause */}
      {rootCause ? (
        <div className={`rounded-xl border px-4 py-4 space-y-2 ${
          reason === "ai_flagged" || reason === "no_qualified"
            ? "border-yellow-400/40 bg-yellow-50/40"
            : "border-accent-2/30 bg-accent-2/5"
        }`}>
          <p className="text-xs font-mono uppercase tracking-widest text-muted">
            {reason === "ai_flagged" || reason === "no_qualified"
              ? "AI-Selected Root Cause (Low Confidence)"
              : "Root Cause"}
          </p>
          <p className="text-sm font-semibold text-foreground">{rootCause.cause_text}</p>
          {rootCause.severity && (
            <p className="text-xs text-muted">
              Severity: <span className="text-foreground font-medium">{rootCause.severity}</span>
            </p>
          )}
          {rootCause.reason && (
            <p className="text-xs text-muted">{rootCause.reason}</p>
          )}
          {rootCause.selection_path && (
            <p className="text-xs font-mono text-muted">
              Path: {rootCause.selection_path}
            </p>
          )}
        </div>
      ) : (
        <div className="rounded-xl border border-foreground/10 bg-surface-strong px-4 py-3">
          <p className="text-xs text-muted italic">
            Root cause details not yet available in the session.
          </p>
        </div>
      )}

      {/* Last iteration causes table (clickable detail) */}
      <LastCausesTable causes={lastCauses} />

      {/* CTA */}
      <div className="pt-1 border-t border-foreground/10 space-y-2">
        <p className="text-xs text-muted">
          Review the root cause above, then proceed to confirm the Action Plan.
        </p>
        <button
          type="button"
          onClick={onContinue}
          className="rounded-xl bg-accent text-surface px-6 py-3 text-sm font-bold
            hover:opacity-90 active:scale-[0.99] transition-all"
        >
          Continue to Action Plan Review &#8594;
        </button>
      </div>
    </div>
  );
}
