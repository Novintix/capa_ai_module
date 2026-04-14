"use client";

import { useState } from "react";

interface Props {
  readonly categories: string[];
  readonly fishboneOutput?: Record<string, unknown> | null;
  readonly onSelect: (category: string) => void;
  readonly loading: boolean;
}

export default function CategorySelectPanel({
  categories,
  fishboneOutput,
  onSelect,
  loading,
}: Props) {
  const [selected, setSelected] = useState<string | null>(null);

  // Build a quick summary of how many causes belong to each category
  const causesByCategory = buildCauseSummary(fishboneOutput);

  function handleConfirm() {
    if (!selected) return;
    onSelect(selected);
  }

  function submitLabel() {
    if (loading) return "Starting Why Analysis\u2026";
    if (selected) return `Proceed with \u201c${selected}\u201d`;
    return "Select a category to continue";
  }

  return (
    <div className="w-full rounded-2xl border border-foreground/10 bg-surface p-6 space-y-5">
      <div>
        <h2 className="text-lg font-bold text-foreground">Select Category for Why Analysis</h2>
        <p className="text-sm text-muted mt-0.5">
          Fishbone analysis is complete. Choose the category you want to drill into
          with Why (5-Why) Analysis.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {categories.map((cat) => {
          const count = causesByCategory[cat] ?? 0;
          const isSelected = selected === cat;

          return (
            <button
              key={cat}
              type="button"
              onClick={() => setSelected(cat)}
              disabled={loading}
              className={`rounded-xl border-2 px-4 py-3 text-left transition-all
                disabled:opacity-50 disabled:cursor-not-allowed
                focus:outline-none focus:ring-2 focus:ring-accent/40
                ${isSelected
                  ? "border-accent bg-accent/10 shadow-sm"
                  : "border-foreground/15 bg-surface-strong hover:border-accent/50"
                }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-semibold text-foreground">{cat}</span>
                {count > 0 && (
                  <span className="text-xs font-mono rounded-full bg-accent/15 text-accent px-2 py-0.5">
                    {count} cause{count === 1 ? "" : "s"}
                  </span>
                )}
              </div>
              {isSelected && (
                <p className="mt-1 text-xs text-accent font-medium">Selected \u2713</p>
              )}
            </button>
          );
        })}
      </div>

      <button
        type="button"
        onClick={handleConfirm}
        disabled={!selected || loading}
        className="w-full rounded-xl bg-accent text-surface py-3 text-sm font-bold
          hover:opacity-90 active:scale-[0.99] transition-all
          disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {submitLabel()}
      </button>
    </div>
  );
}

function safeString(v: unknown): string {
  if (v === null || v === undefined) return "";
  if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") {
    return String(v);
  }
  return "";
}

function tallyCauses(causes: unknown[]): Record<string, number> {
  const summary: Record<string, number> = {};
  for (const cause of causes) {
    if (cause && typeof cause === "object") {
      const cat = safeString((cause as Record<string, unknown>).category).trim();
      if (cat) summary[cat] = (summary[cat] ?? 0) + 1;
    }
  }
  return summary;
}

function buildCauseSummary(
  fishboneOutput: Record<string, unknown> | null | undefined,
): Record<string, number> {
  if (!fishboneOutput) return {};

  for (const key of ["all_categorized_causes", "causes", "high_confidence_causes"]) {
    const causes = fishboneOutput[key];
    if (!Array.isArray(causes) || causes.length === 0) continue;
    const summary = tallyCauses(causes);
    if (Object.keys(summary).length > 0) return summary;
  }

  return {};
}
