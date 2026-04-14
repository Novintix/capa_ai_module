"use client";

import { useState, useEffect } from "react";
import type { WhyHumanReviewInput } from "@/lib/api/rca";

/* -- Types ---------------------------------------------------------------- */

interface ValidatedCause {
  cause_id: string;
  cause_text: string;
  validation_confidence?: number;
  validation_status?: string;
  evidence_match_status?: string;
  validation_rationale?: string;
  process_step?: string;
  failure_mode?: string;
}

interface WhyChainEntry {
  loop: number;
  question: string;
  selected_cause: string;
  decision: string;
  confidence: number;
  human_approved: boolean;
}

interface Props {
  readonly sessionId: string;
  readonly whyOutput: Record<string, unknown>;
  readonly onSubmit: (input: WhyHumanReviewInput) => void;
  readonly loading: boolean;
}

/* -- Helpers -------------------------------------------------------------- */

function safeField(obj: Record<string, unknown>, ...keys: string[]): string {
  for (const k of keys) {
    const v = obj[k];
    if (typeof v === "string" && v) return v;
    if (typeof v === "number") return String(v);
  }
  return "";
}

function isQualified(c: ValidatedCause): boolean {
  return (c.validation_confidence ?? 0) >= 0.9
    && c.evidence_match_status?.toLowerCase() === "matched";
}

function confidenceCls(conf: number): string {
  if (conf >= 0.9) return "bg-accent-2";
  if (conf >= 0.7) return "bg-yellow-400";
  return "bg-danger";
}

function extractCauses(output: Record<string, unknown>): ValidatedCause[] {
  for (const key of ["validated_causes", "causes", "why_causes"]) {
    const list = output[key];
    if (!Array.isArray(list) || list.length === 0) continue;
    const result = list
      .filter((c): c is Record<string, unknown> => c !== null && typeof c === "object")
      .map((c) => ({
        cause_id: safeField(c, "cause_id", "id"),
        cause_text: safeField(c, "cause_text", "text", "cause"),
        validation_confidence:
          typeof c.validation_confidence === "number" ? c.validation_confidence : undefined,
        validation_status:
          typeof c.validation_status === "string" ? c.validation_status : undefined,
        evidence_match_status:
          typeof c.evidence_match_status === "string" ? c.evidence_match_status : undefined,
        validation_rationale:
          typeof c.validation_rationale === "string" ? c.validation_rationale : undefined,
        process_step: typeof c.process_step === "string" ? c.process_step : undefined,
        failure_mode: typeof c.failure_mode === "string" ? c.failure_mode : undefined,
      }))
      .filter((c) => c.cause_id && c.cause_text);
    if (result.length > 0) return result;
  }
  return [];
}

function extractWhyChain(output: Record<string, unknown>): WhyChainEntry[] {
  const list = output.why_chain;
  if (!Array.isArray(list)) return [];
  return list
    .filter((e): e is Record<string, unknown> => e !== null && typeof e === "object")
    .map((e) => ({
      loop: typeof e.loop === "number" ? e.loop : 0,
      question: safeField(e, "question"),
      selected_cause: safeField(e, "selected_cause"),
      decision: safeField(e, "decision"),
      confidence: typeof e.confidence === "number" ? e.confidence : 0,
      human_approved: Boolean(e.human_approved),
    }));
}

/* -- Sub-components ------------------------------------------------------- */

function CauseCard({
  cause,
  isSelected,
  isExpanded,
  onSelect,
  onToggleExpand,
  disabled,
}: Readonly<{
  cause: ValidatedCause;
  isSelected: boolean;
  isExpanded: boolean;
  onSelect: () => void;
  onToggleExpand: () => void;
  disabled: boolean;
}>) {
  const conf = cause.validation_confidence ?? 0;
  const hasDetails = !!(
    cause.validation_rationale ??
    cause.process_step ??
    cause.failure_mode
  );
  const borderCls = isSelected
    ? "border-accent-2 bg-accent-2/8 shadow-sm"
    : "border-foreground/15 bg-surface-strong hover:border-accent-2/40";

  return (
    <div className={`rounded-xl border-2 px-4 py-3 transition-all ${borderCls}`}>
      <button
        type="button"
        onClick={onSelect}
        disabled={disabled}
        className="w-full text-left focus:outline-none"
      >
        <div className="flex items-start justify-between gap-3 mb-2">
          <p className="text-sm text-foreground flex-1">{cause.cause_text}</p>
          <span className="text-xs font-mono font-bold text-muted shrink-0">
            {Math.round(conf * 100)}%
          </span>
        </div>
        <div className="w-full h-1.5 rounded-full bg-foreground/10 overflow-hidden">
          <div
            className={`h-full rounded-full ${confidenceCls(conf)} transition-all`}
            style={{ width: `${conf * 100}%` }}
          />
        </div>
        {isSelected && (
          <p className="mt-1.5 text-xs text-accent-2 font-medium">Selected &#x2713;</p>
        )}
      </button>

      {hasDetails && (
        <button
          type="button"
          onClick={onToggleExpand}
          className="mt-2 text-xs text-muted hover:text-foreground transition-colors flex items-center gap-1.5"
        >
          <span
            className={`inline-block transition-transform duration-150 ${
              isExpanded ? "rotate-90" : ""
            }`}
          >
            &#x25B6;
          </span>
          {isExpanded ? "Hide details" : "View details"}
        </button>
      )}

      {isExpanded && (
        <div className="mt-2 space-y-1 text-xs text-muted border-t border-foreground/10 pt-2">
          {cause.evidence_match_status && (
            <p>
              <span className="font-medium text-foreground">Evidence Match: </span>
              {cause.evidence_match_status}
            </p>
          )}
          {cause.validation_rationale && (
            <p>
              <span className="font-medium text-foreground">Rationale: </span>
              {cause.validation_rationale}
            </p>
          )}
          {cause.process_step && (
            <p>
              <span className="font-medium text-foreground">Process Step: </span>
              {cause.process_step}
            </p>
          )}
          {cause.failure_mode && (
            <p>
              <span className="font-medium text-foreground">Failure Mode: </span>
              {cause.failure_mode}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function WhyHistoryPanel({ chain }: Readonly<{ chain: WhyChainEntry[] }>) {
  const [open, setOpen] = useState(false);
  const plural = chain.length === 1 ? "step" : "steps";
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((s) => !s)}
        className="flex items-center gap-2 text-xs font-semibold text-muted hover:text-foreground transition-colors"
      >
        <span
          className={`inline-block transition-transform duration-150 ${
            open ? "rotate-90" : ""
          }`}
        >
          &#x25B6;
        </span>
        Why Chain History ({chain.length} {plural})
      </button>
      {open && (
        <div className="mt-2 space-y-2 border-l-2 border-accent-2/20 pl-3">
          {chain.map((entry) => (
            <div
              key={`loop-${entry.loop}`}
              className="rounded-lg bg-surface-strong border border-foreground/10 px-3 py-2 text-xs space-y-0.5"
            >
              <p className="font-semibold text-foreground">
                Loop {entry.loop}: {entry.question}
              </p>
              <p className="text-muted">
                &#x2192; <span className="text-foreground">{entry.selected_cause}</span>
              </p>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-mono bg-foreground/8 px-1.5 py-0.5 rounded text-muted">
                  {entry.decision}
                </span>
                {entry.confidence > 0 && (
                  <span className="text-muted">{Math.round(entry.confidence * 100)}%</span>
                )}
                {entry.human_approved && (
                  <span className="text-accent-2">&#x2713; Human approved</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function DecisionButton({
  label,
  sub,
  active,
  onClick,
  colour,
}: Readonly<{
  label: string;
  sub: string;
  active: boolean;
  onClick: () => void;
  colour: "accent" | "accent-2";
}>) {
  const activeCls =
    colour === "accent"
      ? "border-accent bg-accent/10 text-accent"
      : "border-accent-2 bg-accent-2/10 text-accent-2";
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex-1 rounded-lg border-2 px-3 py-2 text-left transition-all focus:outline-none
        ${active ? activeCls : "border-foreground/15 text-muted hover:border-foreground/30"}`}
    >
      <div className="text-sm font-semibold">{label}</div>
      <div className="text-xs opacity-75">{sub}</div>
    </button>
  );
}

/* -- Main component ------------------------------------------------------- */

export default function WhyReviewPanel({
  sessionId,
  whyOutput,
  onSubmit,
  loading,
}: Readonly<Props>) {
  const [selectedCauseId, setSelectedCauseId] = useState<string | null>(null);
  const [decision, setDecision] = useState<"root_cause" | "continue">("root_cause");
  const [expandedCauseId, setExpandedCauseId] = useState<string | null>(null);

  const allCauses = extractCauses(whyOutput);
  const qualifiedCauses = allCauses.filter(isQualified);
  const filteredCount = allCauses.length - qualifiedCauses.length;
  const whyChain = extractWhyChain(whyOutput);

  // Reset selection whenever qualified causes change (e.g. whyOutput prop updated
  // to a next iteration that no longer contains the previously selected cause).
  useEffect(() => {
    if (selectedCauseId && !qualifiedCauses.some((c) => c.cause_id === selectedCauseId)) {
      setSelectedCauseId(null);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [whyOutput]);

  const iteration =
    typeof whyOutput.iteration === "number" ? whyOutput.iteration : 1;
  const depth =
    typeof whyOutput.analysis_depth === "number"
      ? whyOutput.analysis_depth
      : undefined;
  const question = safeField(whyOutput, "current_question", "why_question");

  const isAiFlagged = !!(whyOutput.ai_flagged);

  // ── Zero-Evidence / AI-Flagged guard ─────────────────────────────────────
  // If the backend already concluded via zero-evidence mode (0 qualified causes)
  // we should not be in this panel at all — page.tsx routing handles that via
  // the ai_flagged check. But as a safety net: if we end up here with 0 causes,
  // show a clear informational screen instead of a broken select UI.
  if (qualifiedCauses.length === 0 || isAiFlagged) {
    return (
      <div className="w-full rounded-2xl border border-yellow-400/40 bg-yellow-50/50 p-6 space-y-4">
        <div className="flex items-center gap-2">
          <span className="text-xl">&#x26A0;&#xFE0F;</span>
          <h2 className="text-base font-bold text-yellow-700">
            Why Analysis &#8212; AI Auto-Selected Root Cause
          </h2>
        </div>
        <p className="text-sm text-yellow-700/80">
          No causes met the &#x2265;90% confidence&nbsp;+&nbsp;matched-evidence threshold
          {filteredCount > 0 && (
            <> ({filteredCount} cause{filteredCount === 1 ? " was" : "s were"} generated but fell below threshold)</>
          )}. The AI automatically selected the most critical cause using the{" "}
          <strong>Zero Evidence Agent</strong> (severity, failure-mode, and risk scoring).
        </p>
        <p className="text-xs text-yellow-700 font-semibold">
          &#9888; Manual investigation is recommended before proceeding.
        </p>
        {whyChain.length > 0 && <WhyHistoryPanel chain={whyChain} />}
      </div>
    );
  }

  function handleSubmit() {
    if (!selectedCauseId) return;
    onSubmit({ session_id: sessionId, selected_cause_id: selectedCauseId, decision });
  }

  function submitLabel(): string {
    if (loading) return "Submitting\u2026";
    if (!selectedCauseId) return "Select a qualified cause to continue";
    if (decision === "root_cause") return "Confirm Root Cause";
    return "Continue Analysis";
  }

  function toggleExpand(id: string) {
    setExpandedCauseId((prev) => (prev === id ? null : id));
  }

  return (
    <div className="w-full rounded-2xl border border-foreground/10 bg-surface p-6 space-y-5">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 flex-wrap mb-1">
          <h2 className="text-lg font-bold text-foreground">
            Why Analysis &#8212; Human Review
          </h2>
          <span className="text-xs font-mono rounded-full bg-accent-2/15 text-accent-2 px-2 py-0.5">
            Iteration {iteration}
          </span>
          {depth !== undefined && (
            <span className="text-xs font-mono rounded-full bg-foreground/8 text-muted px-2 py-0.5">
              Depth {depth}
            </span>
          )}
        </div>
        {question && (
          <p className="text-sm text-muted italic mt-1">&ldquo;{question}&rdquo;</p>
        )}
        <p className="text-sm text-muted mt-2">
          Select the most relevant cause (&#x2265;90% confidence + matched evidence),
          then decide whether this is the{" "}
          <strong>Root Cause</strong> or to <strong>Continue</strong> deeper.
        </p>
      </div>

      {/* Why chain history */}
      {whyChain.length > 0 && <WhyHistoryPanel chain={whyChain} />}

      {/* Qualified count banner */}
      <div className="flex flex-wrap gap-2 items-center">
        <span className="text-xs rounded-full bg-accent-2/15 text-accent-2 px-3 py-1 font-medium">
          {qualifiedCauses.length} qualified{" "}
          {qualifiedCauses.length === 1 ? "cause" : "causes"} (&#x2265;90% + matched)
        </span>
        {filteredCount > 0 && (
          <span className="text-xs rounded-full bg-foreground/8 text-muted px-3 py-1">
            {filteredCount} filtered out (low confidence or unmatched)
          </span>
        )}
      </div>

      {/* Cause cards */}
      {qualifiedCauses.length === 0 ? (
        <p className="text-sm text-muted italic">
          No causes met the &#x2265;90% confidence + matched evidence threshold.
        </p>
      ) : (
        <div className="space-y-3">
          {qualifiedCauses.map((cause) => (
            <CauseCard
              key={cause.cause_id}
              cause={cause}
              isSelected={selectedCauseId === cause.cause_id}
              isExpanded={expandedCauseId === cause.cause_id}
              onSelect={() => setSelectedCauseId(cause.cause_id)}
              onToggleExpand={() => toggleExpand(cause.cause_id)}
              disabled={loading}
            />
          ))}
        </div>
      )}

      {/* Decision */}
      {selectedCauseId && (
        <div className="rounded-xl border border-foreground/10 bg-surface-strong p-4">
          <p className="text-xs font-mono uppercase tracking-widest text-muted mb-3">
            Decision
          </p>
          <div className="flex gap-3">
            <DecisionButton
              label="Root Cause"
              sub="End the analysis here"
              active={decision === "root_cause"}
              onClick={() => setDecision("root_cause")}
              colour="accent"
            />
            <DecisionButton
              label="Continue"
              sub="Ask &#x2018;Why?&#x2019; again"
              active={decision === "continue"}
              onClick={() => setDecision("continue")}
              colour="accent-2"
            />
          </div>
        </div>
      )}

      {/* Submit */}
      <button
        type="button"
        onClick={handleSubmit}
        disabled={!selectedCauseId || loading}
        className="w-full rounded-xl bg-accent-2 text-surface py-3 text-sm font-bold
          hover:opacity-90 active:scale-[0.99] transition-all
          disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {submitLabel()}
      </button>
    </div>
  );
}
