"use client";

import { useState } from "react";
import type { RCAResponse } from "@/lib/api/rca";

/* -- Types ---------------------------------------------------------------- */

interface RootCauseDetail {
  cause_text: string;
  severity?: string;
  selection_path?: string;
  reason?: string;
  process_step?: string;
  failure_mode?: string;
  potential_effects?: string;
  current_controls?: string;
}

interface WCEntry {
  loop: number;
  question: string;
  selected_cause: string;
  decision: string;
  confidence: number;
  human_approved: boolean;
}

interface GeneratedCause { cause_id: string; cause_text: string }

interface ValidatedItem {
  cause_id: string;
  cause_text: string;
  validation_confidence?: number;
  evidence_match_status?: string;
}

interface IterOut {
  iteration: number;
  question: string;
  question_reasoning?: string;
  generated_causes: GeneratedCause[];
  total_generated: number;
  fmea_matched: number;
  validated_causes: ValidatedItem[];
  total_validated: number;
  selected_cause?: GeneratedCause | null;
  human_decision?: string;
}

interface ValSummary {
  total_input_causes: number;
  total_validated_causes: number;
  overall_confidence?: number;
}

interface Props {
  readonly response: RCAResponse;
  readonly onConfirm: () => void;
  readonly onReject: () => void;
  readonly onStartNew: () => void;
  readonly loading: boolean;
  readonly confirmed?: boolean;
}

/* -- Helpers -------------------------------------------------------------- */

function sf(obj: Record<string, unknown>, ...keys: string[]): string {
  for (const k of keys) {
    const v = obj[k];
    if (typeof v === "string" && v) return v;
  }
  return "";
}

function sn(obj: Record<string, unknown>, k: string): number {
  const v = obj[k];
  return typeof v === "number" ? v : 0;
}

function extractRootCause(wo: Record<string, unknown>): RootCauseDetail | null {
  const rc = wo.root_cause;
  if (rc && typeof rc === "object") {
    const r = rc as Record<string, unknown>;
    const text = sf(r, "cause_text", "text");
    if (!text) return null;
    return {
      cause_text: text,
      severity: sf(r, "severity") || undefined,
      selection_path: sf(r, "selection_path") || undefined,
      reason: sf(r, "reason") || undefined,
      process_step: sf(r, "process_step") || undefined,
      failure_mode: sf(r, "failure_mode") || undefined,
      potential_effects: sf(r, "potential_effects") || undefined,
      current_controls: sf(r, "current_controls") || undefined,
    };
  }
  const text = sf(wo, "root_cause_text", "final_root_cause", "conclusion");
  return text ? { cause_text: text } : null;
}

function extractSimpleChain(wo: Record<string, unknown>): string[] {
  const list = wo.why_chain;
  if (!Array.isArray(list)) return [];
  return list
    .map((item) => {
      if (typeof item === "string") return item;
      if (item && typeof item === "object") {
        const r = item as Record<string, unknown>;
        return sf(r, "cause_text", "question", "cause", "text");
      }
      return "";
    })
    .filter(Boolean);
}

function extractChainEntries(wo: Record<string, unknown>): WCEntry[] {
  const list = wo.why_chain;
  if (!Array.isArray(list)) return [];
  return list
    .filter((e): e is Record<string, unknown> => e !== null && typeof e === "object" && "loop" in e)
    .map((e) => ({
      loop: typeof e.loop === "number" ? e.loop : 0,
      question: sf(e, "question"),
      selected_cause: sf(e, "selected_cause"),
      decision: sf(e, "decision"),
      confidence: typeof e.confidence === "number" ? e.confidence : 0,
      human_approved: Boolean(e.human_approved),
    }));
}

function parseCauseList(raw: unknown): GeneratedCause[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((c): c is Record<string, unknown> => c !== null && typeof c === "object")
    .map((c) => ({ cause_id: sf(c, "cause_id", "id"), cause_text: sf(c, "cause_text", "text", "cause") }))
    .filter((c) => c.cause_id && c.cause_text);
}

function parseValidated(raw: unknown): ValidatedItem[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((c): c is Record<string, unknown> => c !== null && typeof c === "object")
    .map((c) => ({
      cause_id: sf(c, "cause_id", "id"),
      cause_text: sf(c, "cause_text", "text", "cause"),
      validation_confidence: typeof c.validation_confidence === "number" ? c.validation_confidence : undefined,
      evidence_match_status: typeof c.evidence_match_status === "string" ? c.evidence_match_status : undefined,
    }))
    .filter((c) => c.cause_id && c.cause_text);
}

function extractIterations(wo: Record<string, unknown>): IterOut[] {
  const list = wo.iteration_outputs;
  if (!Array.isArray(list)) return [];
  return list
    .filter((it): it is Record<string, unknown> => it !== null && typeof it === "object")
    .map((it) => {
      const sel = it.selected_cause;
      let selected: GeneratedCause | null = null;
      if (sel && typeof sel === "object") {
        const s = sel as Record<string, unknown>;
        const id = sf(s, "cause_id", "id");
        const txt = sf(s, "cause_text", "text", "cause");
        selected = id && txt ? { cause_id: id, cause_text: txt } : null;
      }
      return {
        iteration: typeof it.iteration === "number" ? it.iteration : 0,
        question: sf(it, "question"),
        question_reasoning: sf(it, "question_reasoning") || undefined,
        generated_causes: parseCauseList(it.generated_causes),
        total_generated: sn(it, "total_generated"),
        fmea_matched: sn(it, "fmea_matched"),
        validated_causes: parseValidated(it.validated_causes),
        total_validated: sn(it, "total_validated"),
        selected_cause: selected,
        human_decision: sf(it, "human_decision") || undefined,
      };
    });
}

function extractValSummary(wo: Record<string, unknown>): ValSummary | null {
  const vs = wo.validation_summary;
  if (!vs || typeof vs !== "object") return null;
  const r = vs as Record<string, unknown>;
  return {
    total_input_causes: sn(r, "total_input_causes"),
    total_validated_causes: sn(r, "total_validated_causes"),
    overall_confidence: typeof r.overall_confidence === "number" ? r.overall_confidence : undefined,
  };
}

function downloadJson(data: unknown, filename: string) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/* -- Sub-components ------------------------------------------------------- */

function Stat({ label, value }: Readonly<{ label: string; value: string | number }>) {
  return (
    <div className="rounded-xl bg-surface-strong border border-foreground/10 px-4 py-3 text-center">
      <p className="text-xl font-bold text-foreground">{value}</p>
      <p className="text-xs text-muted mt-0.5">{label}</p>
    </div>
  );
}

function IterationCard({ it }: Readonly<{ it: IterOut }>) {
  const [open, setOpen] = useState(false);
  const qualified = it.validated_causes.filter(
    (c) => (c.validation_confidence ?? 0) >= 0.9 && c.evidence_match_status?.toLowerCase() === "matched",
  );
  return (
    <div className="rounded-xl border border-foreground/10 bg-surface-strong overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((s) => !s)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-foreground/3 transition-colors"
      >
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-xs font-mono bg-accent-2/15 text-accent-2 rounded-full px-2 py-0.5 shrink-0">
            #{it.iteration}
          </span>
          <span className="text-sm font-medium text-foreground truncate">
            {it.question || "(no question)"}
          </span>
        </div>
        <span className={`text-xs text-muted ml-2 shrink-0 transition-transform duration-150 ${open ? "rotate-90" : ""}`}>
          &#x25B6;
        </span>
      </button>
      {open && (
        <div className="px-4 pb-4 space-y-3 border-t border-foreground/10 pt-3">
          {it.question_reasoning && (
            <p className="text-xs text-muted">{it.question_reasoning}</p>
          )}
          <div>
            <p className="text-xs font-semibold text-foreground mb-1">
              Generated ({it.total_generated})
              {it.fmea_matched > 0 && (
                <span className="text-muted font-normal"> &middot; {it.fmea_matched} FMEA matched</span>
              )}
            </p>
            {it.generated_causes.slice(0, 3).map((c) => (
              <p key={c.cause_id} className="text-xs text-muted">
                &middot; <span className="font-mono text-foreground">{c.cause_id}</span>:{" "}
                {c.cause_text.length > 80 ? `${c.cause_text.slice(0, 80)}\u2026` : c.cause_text}
              </p>
            ))}
            {it.generated_causes.length > 3 && (
              <p className="text-xs text-muted">&hellip; and {it.generated_causes.length - 3} more</p>
            )}
          </div>
          <div>
            <p className="text-xs font-semibold text-foreground mb-1">
              Validated ({it.total_validated})
              <span className="text-muted font-normal"> &middot; {qualified.length} qualified (&#x2265;90%)</span>
            </p>
            {qualified.slice(0, 3).map((c) => (
              <p key={c.cause_id} className="text-xs text-muted">
                &middot; <span className="font-mono text-foreground">{c.cause_id}</span>
                {c.validation_confidence !== undefined && (
                  <span> ({Math.round(c.validation_confidence * 100)}%)</span>
                )}:{" "}
                {c.cause_text.length > 80 ? `${c.cause_text.slice(0, 80)}\u2026` : c.cause_text}
              </p>
            ))}
            {qualified.length > 3 && (
              <p className="text-xs text-muted">&hellip; and {qualified.length - 3} more</p>
            )}
          </div>
          {it.selected_cause && (
            <div className="rounded-lg border border-accent-2/30 bg-accent-2/5 px-3 py-2">
              <p className="text-xs font-semibold text-foreground">
                &#127919; {it.selected_cause.cause_id}: {it.selected_cause.cause_text}
              </p>
              {it.human_decision && (
                <p className="text-xs text-muted mt-0.5">
                  Decision: <span className="font-mono text-foreground">{it.human_decision}</span>
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function WhyChainSummaryPanel({ entries }: Readonly<{ entries: WCEntry[] }>) {
  const [open, setOpen] = useState(false);
  const plural = entries.length === 1 ? "loop" : "loops";
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((s) => !s)}
        className="flex items-center gap-2 text-sm font-semibold text-foreground hover:text-accent transition-colors"
      >
        <span className={`transition-transform duration-150 ${open ? "rotate-90" : ""}`}>&#x25B6;</span>
        Why Chain Summary ({entries.length} {plural})
      </button>
      {open && (
        <div className="mt-2 space-y-2">
          {entries.map((e) => (
            <div
              key={`wc-${e.loop}`}
              className="rounded-xl border border-foreground/10 bg-surface-strong px-4 py-3 space-y-1"
            >
              <p className="text-sm font-semibold text-foreground">
                Loop {e.loop}: {e.question}
              </p>
              <p className="text-xs text-muted">&#x2192; {e.selected_cause}</p>
              <div className="flex items-center gap-3 flex-wrap">
                <span className="font-mono text-xs bg-foreground/8 px-1.5 py-0.5 rounded text-muted">
                  {e.decision}
                </span>
                {e.confidence > 0 && (
                  <span className="text-xs text-muted">{Math.round(e.confidence * 100)}%</span>
                )}
                {e.human_approved && (
                  <span className="text-xs text-accent-2">&#x2713; Human approved</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* -- Completed view ------------------------------------------------------- */

function CompletedView({
  response,
  onStartNew,
}: Readonly<{ response: RCAResponse; onStartNew: () => void }>) {
  const wo = (response.why_output ?? {}) as Record<string, unknown>;
  const rootCause = extractRootCause(wo);
  const simpleChain = extractSimpleChain(wo);

  return (
    <div className="w-full rounded-2xl border border-accent-2/30 bg-accent-2/5 p-6 space-y-5">
      <div className="flex items-center gap-3">
        <span className="text-3xl">&#x2705;</span>
        <div>
          <h2 className="text-lg font-bold text-foreground">RCA Complete</h2>
          <p className="text-sm text-muted mt-0.5">
            Approved &#8212; ready to proceed to Action Plan.
          </p>
        </div>
      </div>

      {rootCause && (
        <div className="rounded-xl border border-accent-2/30 bg-surface p-4 space-y-1">
          <p className="text-xs font-mono uppercase tracking-widest text-muted">Root Cause</p>
          <p className="text-sm font-semibold text-foreground">{rootCause.cause_text}</p>
        </div>
      )}

      {simpleChain.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-mono uppercase tracking-widest text-muted">Why Chain</p>
          <ol className="space-y-1.5">
            {simpleChain.map((step) => (
              <li key={step} className="flex gap-3 text-sm">
                <span className="shrink-0 rounded-full bg-accent-2/15 text-accent-2 text-xs font-bold w-5 h-5 flex items-center justify-center mt-0.5">
                  &#x2713;
                </span>
                <span className="text-foreground">{step}</span>
              </li>
            ))}
          </ol>
        </div>
      )}

      <div className="pt-2 flex items-center gap-3">
        <a
          href={response.action_plan_endpoint ?? "#"}
          className="rounded-xl bg-accent-2 text-surface px-6 py-3 text-sm font-bold hover:opacity-90 active:scale-[0.99] transition-all inline-block"
        >
          Open Action Plan &#8594;
        </a>
        <button
          type="button"
          onClick={onStartNew}
          className="text-sm text-muted hover:text-foreground transition-colors underline underline-offset-2"
        >
          Start new analysis
        </button>
      </div>
    </div>
  );
}

/* -- Confirm view --------------------------------------------------------- */

function ConfirmView({
  response,
  onConfirm,
  onReject,
  loading,
  confirmed,
}: Readonly<Omit<Props, "onStartNew">>) {
  const [showExtra, setShowExtra] = useState(false);
  const wo = (response.why_output ?? {}) as Record<string, unknown>;
  const isAiFlagged = wo.status === "ai_flagged";
  const rootCause = extractRootCause(wo);
  const chainEntries = extractChainEntries(wo);
  const iterations = extractIterations(wo);
  const valSummary = extractValSummary(wo);
  const depth = typeof wo.analysis_depth === "number" ? wo.analysis_depth : undefined;
  const execTime =
    typeof wo.execution_time_seconds === "number" ? wo.execution_time_seconds : undefined;
  const stoppingReason = sf(wo, "stopping_reason");
  const hasExtra =
    !!(rootCause?.severity ?? rootCause?.process_step ?? rootCause?.failure_mode);

  function handleDownload() {
    downloadJson(response.why_output ?? response, `why_analysis_${response.complaint_id}_${Date.now()}.json`);
  }

  function confirmLabel(): string {
    if (loading) return "Confirming\u2026";
    return "Yes, proceed to Action Plan";
  }

  return (
    <div className="w-full rounded-2xl border border-foreground/10 bg-surface p-6 space-y-6">
      {/* Header */}
      {isAiFlagged ? (
        <div className="rounded-xl border border-yellow-400/40 bg-yellow-50/50 px-4 py-3">
          <p className="text-sm font-bold text-yellow-700">
            &#9888; AI Auto-Selected &#8212; Manual Verification Recommended
          </p>
          <p className="text-xs text-yellow-600 mt-1">
            All causes were below the 90% confidence threshold. The AI automatically selected the
            most critical cause based on severity and failure mode analysis.
          </p>
        </div>
      ) : (
        <div>
          <h2 className="text-lg font-bold text-foreground">Proceed to Action Plan?</h2>
          <p className="text-sm text-muted mt-0.5">
            Why Analysis is complete. Review the results below and confirm to proceed.
          </p>
        </div>
      )}

      {/* Root cause */}
      {rootCause && (
        <div className="rounded-xl border border-foreground/15 bg-surface-strong p-4 space-y-2">
          <p className="text-xs font-mono uppercase tracking-widest text-muted">
            {isAiFlagged ? "AI-Selected Root Cause" : "Identified Root Cause"}
          </p>
          <p className="text-sm font-semibold text-foreground">{rootCause.cause_text}</p>
          {rootCause.reason && (
            <p className="text-xs text-muted">{rootCause.reason}</p>
          )}
          {rootCause.selection_path && (
            <p className="text-xs text-muted font-mono">Path: {rootCause.selection_path}</p>
          )}
        </div>
      )}

      {/* Stats row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {depth !== undefined && <Stat label="Analysis Depth" value={depth} />}
        {execTime !== undefined && (
          <Stat label="Execution Time" value={`${execTime.toFixed(1)}s`} />
        )}
        {chainEntries.length > 0 && (
          <Stat label="Why Chain" value={chainEntries.length} />
        )}
        {valSummary?.overall_confidence !== undefined && (
          <Stat
            label="Overall Confidence"
            value={`${Math.round(valSummary.overall_confidence * 100)}%`}
          />
        )}
      </div>

      {/* Additional root cause details */}
      {hasExtra && (
        <div>
          <button
            type="button"
            onClick={() => setShowExtra((s) => !s)}
            className="flex items-center gap-2 text-xs font-semibold text-muted hover:text-foreground transition-colors"
          >
            <span className={`transition-transform duration-150 ${showExtra ? "rotate-90" : ""}`}>&#x25B6;</span>
            {" "}Additional Details
          </button>
          {showExtra && (
            <div className="mt-2 rounded-xl border border-foreground/10 bg-surface-strong px-4 py-3 space-y-1 text-xs">
              {rootCause?.severity && (
                <p>
                  <span className="font-medium text-foreground">Severity: </span>
                  <span className="text-muted">{rootCause.severity}</span>
                </p>
              )}
              {rootCause?.process_step && (
                <p>
                  <span className="font-medium text-foreground">Process Step: </span>
                  <span className="text-muted">{rootCause.process_step}</span>
                </p>
              )}
              {rootCause?.failure_mode && (
                <p>
                  <span className="font-medium text-foreground">Failure Mode: </span>
                  <span className="text-muted">{rootCause.failure_mode}</span>
                </p>
              )}
              {rootCause?.potential_effects && (
                <p>
                  <span className="font-medium text-foreground">Potential Effects: </span>
                  <span className="text-muted">{rootCause.potential_effects}</span>
                </p>
              )}
              {rootCause?.current_controls && (
                <p>
                  <span className="font-medium text-foreground">Current Controls: </span>
                  <span className="text-muted">{rootCause.current_controls}</span>
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {/* Iteration details */}
      {iterations.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm font-semibold text-foreground">
            Iteration Details ({iterations.length})
          </p>
          {iterations.map((it) => (
            <IterationCard key={`iter-${it.iteration}`} it={it} />
          ))}
        </div>
      )}

      {/* Why chain summary */}
      {chainEntries.length > 0 && <WhyChainSummaryPanel entries={chainEntries} />}

      {/* Validation summary */}
      {valSummary && (
        <div className="rounded-xl border border-foreground/10 bg-surface-strong px-4 py-3">
          <p className="text-xs font-mono uppercase tracking-widest text-muted mb-2">
            Validation Summary
          </p>
          <div className="flex gap-6 flex-wrap text-sm">
            <p>
              <span className="text-muted">Input causes: </span>
              <span className="font-semibold text-foreground">{valSummary.total_input_causes}</span>
            </p>
            <p>
              <span className="text-muted">Validated: </span>
              <span className="font-semibold text-foreground">
                {valSummary.total_validated_causes}
              </span>
            </p>
            {valSummary.overall_confidence !== undefined && (
              <p>
                <span className="text-muted">Confidence: </span>
                <span className="font-semibold text-foreground">
                  {Math.round(valSummary.overall_confidence * 100)}%
                </span>
              </p>
            )}
          </div>
        </div>
      )}

      {stoppingReason && (
        <p className="text-xs text-muted italic">Stopping reason: {stoppingReason}</p>
      )}

      {/* Actions */}
      <div className="space-y-3 pt-1 border-t border-foreground/10">
        <button
          type="button"
          onClick={handleDownload}
          className="text-xs text-muted hover:text-foreground transition-colors flex items-center gap-1.5"
        >
          &#x2B07; Download full report (JSON)
        </button>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={onConfirm}
            disabled={loading}
            className="rounded-xl bg-accent text-surface px-6 py-3 text-sm font-bold
              hover:opacity-90 active:scale-[0.99] transition-all
              disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {confirmLabel()}
          </button>
          <button
            type="button"
            onClick={onReject}
            disabled={loading}
            className="rounded-xl border-2 border-danger text-danger px-6 py-3 text-sm font-bold
              hover:bg-danger/5 active:scale-[0.99] transition-all
              disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Not yet
          </button>
        </div>
        {confirmed === false && (
          <p className="text-xs text-muted">
            Session remains open. Review and confirm when ready.
          </p>
        )}
      </div>
    </div>
  );
}

/* -- Main export ---------------------------------------------------------- */

export default function ActionPlanPanel({
  response,
  onConfirm,
  onReject,
  onStartNew,
  loading,
  confirmed,
}: Readonly<Props>) {
  if (response.phase === "completed") {
    return <CompletedView response={response} onStartNew={onStartNew} />;
  }
  return (
    <ConfirmView
      response={response}
      onConfirm={onConfirm}
      onReject={onReject}
      loading={loading}
      confirmed={confirmed}
    />
  );
}
