"use client";

import { useState } from "react";
import type { FishboneCauseDecision } from "@/lib/api/rca";

interface Cause {
  cause_id: string;
  cause_text: string;
  category?: string;
  validation_confidence?: number;
  validation_status?: string;
}

interface Props {
  readonly causes: Cause[];
  readonly onSubmit: (decisions: FishboneCauseDecision[]) => void;
  readonly loading: boolean;
}

type Action = "RCA" | "PROCEED" | "DISMISS";

interface DecisionRow {
  cause_id: string;
  action: Action;
  comment: string;
}

const ACTION_STYLES: Record<Action, string> = {
  RCA: "bg-accent text-surface border-accent",
  PROCEED: "bg-accent-2 text-surface border-accent-2",
  DISMISS: "bg-muted/40 text-foreground border-muted/40",
};

const ACTION_LABELS: Record<Action, string> = {
  RCA: "Root Cause",
  PROCEED: "Proceed",
  DISMISS: "Dismiss",
};

export default function FishboneDecidePanel({ causes, onSubmit, loading }: Props) {
  const [rows, setRows] = useState<DecisionRow[]>(() =>
    causes.map((c) => ({ cause_id: c.cause_id, action: "PROCEED", comment: "" })),
  );
  const [showComments, setShowComments] = useState<Record<string, boolean>>({});

  function setAction(causeId: string, action: Action) {
    setRows((r) => r.map((row) => (row.cause_id === causeId ? { ...row, action } : row)));
  }

  function setComment(causeId: string, comment: string) {
    setRows((r) => r.map((row) => (row.cause_id === causeId ? { ...row, comment } : row)));
  }

  function toggleComment(causeId: string) {
    setShowComments((s) => ({ ...s, [causeId]: !s[causeId] }));
  }

  function handleSubmit() {
    const decisions: FishboneCauseDecision[] = rows.map((r) => ({
      cause_id: r.cause_id,
      action: r.action,
      comment: r.comment.trim() || undefined,
    }));
    onSubmit(decisions);
  }

  const rcaCount = rows.filter((r) => r.action === "RCA").length;
  const proceedCount = rows.filter((r) => r.action === "PROCEED").length;
  const dismissCount = rows.filter((r) => r.action === "DISMISS").length;

  return (
    <div className="w-full rounded-2xl border border-foreground/10 bg-surface p-6 space-y-5">
      <div>
        <h2 className="text-lg font-bold text-foreground">Fishbone — Review Causes</h2>
        <p className="text-sm text-muted mt-0.5">
          {causes.length} high-confidence cause{causes.length === 1 ? "" : "s"} need your
          decision. Mark each as{" "}
          <strong className="text-accent">Root Cause</strong>,{" "}
          <strong className="text-accent-2">Proceed</strong>, or{" "}
          <strong className="text-muted">Dismiss</strong>.
        </p>
      </div>

      {/* Summary chips */}
      <div className="flex gap-3 text-xs">
        <Chip label="Root Cause" count={rcaCount} colour="text-accent" />
        <Chip label="Proceed" count={proceedCount} colour="text-accent-2" />
        <Chip label="Dismiss" count={dismissCount} colour="text-muted" />
      </div>

      {/* Cause rows */}
      <div className="space-y-3">
        {causes.map((cause, idx) => {
          const row = rows[idx];
          const showCmt = showComments[cause.cause_id] ?? false;

          return (
            <div
              key={cause.cause_id}
              className="rounded-xl border border-foreground/10 bg-surface-strong p-4 space-y-3"
            >
              {/* Cause header */}
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    {cause.category && (
                      <span className="text-xs font-mono rounded-full border border-foreground/15 px-2 py-0.5 text-muted">
                        {cause.category}
                      </span>
                    )}
                    {cause.validation_confidence !== undefined && (
                      <span className="text-xs text-muted">
                        {Math.round(cause.validation_confidence * 100)}% confidence
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-foreground">{cause.cause_text}</p>
                </div>
              </div>

              {/* Action buttons */}
              <div className="flex flex-wrap gap-2">
                {(["RCA", "PROCEED", "DISMISS"] as Action[]).map((action) => (
                  <button
                    key={action}
                    type="button"
                    onClick={() => setAction(cause.cause_id, action)}
                    disabled={loading}
                    className={`rounded-lg border px-3 py-1.5 text-xs font-semibold transition-all
                      disabled:opacity-50 disabled:cursor-not-allowed
                      ${row.action === action ? ACTION_STYLES[action] : "bg-transparent border-foreground/20 text-muted hover:border-foreground/40"}`}
                  >
                    {ACTION_LABELS[action]}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => toggleComment(cause.cause_id)}
                  className="ml-auto text-xs text-muted hover:text-foreground transition-colors"
                >
                  {showCmt ? "Hide note" : "Add note"}
                </button>
              </div>

              {showCmt && (
                <textarea
                  value={row.comment}
                  onChange={(e) => setComment(cause.cause_id, e.target.value)}
                  rows={2}
                  placeholder="Optional note for this decision…"
                  className="w-full rounded-lg border border-foreground/15 px-3 py-2 text-sm bg-surface
                    text-foreground placeholder:text-muted/50 focus:outline-none focus:ring-2
                    focus:ring-accent/40 resize-none"
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Submit */}
      <button
        type="button"
        onClick={handleSubmit}
        disabled={loading}
        className="w-full rounded-xl bg-accent text-surface py-3 text-sm font-bold
          hover:opacity-90 active:scale-[0.99] transition-all
          disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {(() => {
          if (loading) return "Submitting…";
          const plural = causes.length === 1 ? "" : "s";
          return `Submit ${causes.length} Decision${plural}`;
        })()}
      </button>
    </div>
  );
}

function Chip({
  label,
  count,
  colour,
}: Readonly<{
  label: string;
  count: number;
  colour: string;
}>) {
  return (
    <span className={`font-medium ${colour}`}>
      {count} {label}
    </span>
  );
}
