"use client";

import type { RCAResponse } from "@/lib/api/rca";

const PHASE_LABELS: Record<string, string> = {
  idle: "Idle",
  fishbone_running: "Fishbone Running",
  why_running: "Why Analysis Running",
  completed: "Completed",
  error: "Error",
};

const PHASE_COLOURS: Record<string, string> = {
  idle: "bg-muted/20 text-muted",
  fishbone_running: "bg-accent/15 text-accent",
  why_running: "bg-accent-2/15 text-accent-2",
  completed: "bg-accent-2/15 text-accent-2",
  error: "bg-danger/15 text-danger",
};

interface Props {
  readonly response: RCAResponse;
  readonly loading?: boolean;
}

export default function RCAStatusPanel({ response, loading }: Props) {
  const phaseLabel = PHASE_LABELS[response.phase] ?? response.phase;
  const phaseColour = PHASE_COLOURS[response.phase] ?? "bg-muted/20 text-muted";

  return (
    <div className="w-full rounded-2xl border border-foreground/10 bg-surface p-5 space-y-4">
      {/* Top row */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <p className="text-xs font-mono text-muted uppercase tracking-widest mb-0.5">
            Session
          </p>
          <p className="text-base font-bold text-foreground font-mono">
            {response.complaint_id}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {loading && (
            <span className="inline-flex items-center gap-1.5 text-xs text-muted">
              <span className="inline-block h-3 w-3 rounded-full border-2 border-muted border-t-accent animate-spin" />{" "}
              Processing…
            </span>
          )}
          <span className={`text-xs font-semibold rounded-full px-3 py-1 ${phaseColour}`}>
            {phaseLabel}
          </span>
        </div>
      </div>

      {/* Message */}
      {response.message && (
        <div className="rounded-lg bg-surface-strong border border-foreground/8 px-4 py-3 text-sm text-foreground">
          {response.message}
        </div>
      )}

      {/* Error */}
      {response.error && (
        <div className="rounded-lg bg-danger/10 border border-danger/30 px-4 py-3 text-sm text-danger">
          <strong>Error:</strong> {response.error}
        </div>
      )}

      {/* Pills row */}
      <div className="flex flex-wrap gap-2 text-xs">
        {response.selected_method && (
          <Pill label="Method" value={response.selected_method} />
        )}
        {response.selected_category && (
          <Pill label="Category" value={response.selected_category} />
        )}
        {response.why_session_id && (
          <Pill label="Why Session" value={response.why_session_id.slice(0, 8) + "…"} mono />
        )}
      </div>
    </div>
  );
}

function Pill({
  label,
  value,
  mono,
}: Readonly<{
  label: string;
  value: string;
  mono?: boolean;
}>) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-foreground/15 bg-surface px-2.5 py-1 text-foreground">
      <span className="text-muted">{label}:</span>
      <span className={mono ? "font-mono" : "font-medium"}>{value}</span>
    </span>
  );
}
