"use client";

import { useState, useEffect, useCallback } from "react";
import { buildPayloadFromDraft, createEmptyDraft, loadDraftFromStorage, saveDraftToStorage } from "@/lib/rca-intake";
import type { RCAIntakeDraft } from "@/lib/rca-intake";
import type { RCAStartInput } from "@/lib/api/rca";

interface Props {
  readonly onSubmit: (payload: RCAStartInput, method: "why" | "fishbone") => void;
  readonly loading: boolean;
}

interface FieldDef {
  key: keyof RCAIntakeDraft;
  label: string;
  required?: boolean;
  rows?: number;
  placeholder?: string;
  hint?: string;
}

const REQUIRED_FIELDS: FieldDef[] = [
  {
    key: "complaint_id",
    label: "Complaint ID",
    required: true,
    rows: 1,
    placeholder: "e.g. CAPA-2026-0042",
    hint: "Unique identifier for this complaint record.",
  },
  {
    key: "complaint",
    label: "Complaint / Problem Statement",
    required: true,
    rows: 4,
    placeholder: "Describe the issue clearly and concisely…",
    hint: "The core problem that needs root cause analysis.",
  },
];

const OPTIONAL_FIELDS: FieldDef[] = [
  {
    key: "evidence",
    label: "Evidence",
    rows: 3,
    placeholder: "Observations, measurements, data points…",
    hint: "Supporting facts that describe or quantify the issue.",
  },
  {
    key: "sop",
    label: "SOP Reference",
    rows: 2,
    placeholder: "Paste relevant SOP text or reference code…",
    hint: "Standard Operating Procedure context relevant to the problem.",
  },
  {
    key: "fmea_document_path",
    label: "FMEA Document Path",
    rows: 1,
    placeholder: "/data/fmea/tablet-weight-fmea.xlsx",
    hint: "File path to the FMEA Excel document (optional).",
  },
  {
    key: "evidence_files",
    label: "Evidence File Paths",
    rows: 2,
    placeholder: "One path per line, or comma-separated. PDFs, images, logs…",
    hint: "List of evidence file paths.",
  },
  {
    key: "logs",
    label: "System / Process Logs",
    rows: 3,
    placeholder: "Paste relevant log excerpts…",
  },
  {
    key: "reports",
    label: "Investigation Reports",
    rows: 3,
    placeholder: "Paste or summarise existing investigation reports…",
  },
  {
    key: "process_data",
    label: "Process Data",
    rows: 3,
    placeholder: "Batch records, sensor readings, yield data…",
  },
  {
    key: "historical_capa",
    label: "Historical CAPA Records",
    rows: 3,
    placeholder: "Past CAPAs related to this issue or similar problems…",
  },
  {
    key: "policies",
    label: "Relevant Policies",
    rows: 2,
    placeholder: "Regulatory or internal policies that apply…",
  },
  {
    key: "investigation_records",
    label: "Investigation Records",
    rows: 3,
    placeholder: "Detailed investigation notes or findings…",
  },
  {
    key: "supporting_system_information",
    label: "Supporting System Information",
    rows: 2,
    placeholder: "ERP data, LIMS output, instrument info…",
  },
];

const EXAMPLE_DRAFT: Partial<RCAIntakeDraft> = {
  complaint_id: "CAPA-2024-001",
  complaint:
    "Multiple batches of tablets showing incorrect weight. Batch #2024-TBL-045 had tablets weighing 520mg instead of specified 500mg \u00b15%. Quality control detected 15 out of 100 tablets outside specification during routine sampling.",
  evidence:
    "Batch records show compression force was set at 12kN instead of specified 10kN. Load cell calibration certificate dated 6 months ago. Operator training records current. Weight monitoring system flagged deviation at 14:30 on production line 2.",
  sop:
    "SOP-PROD-001: Tablet Compression requires compression force verification before each batch. Weight checks every 30 minutes. Calibration quarterly. Acceptable range: 500mg \u00b15% (475\u2013525mg).",
  fmea_document_path: "fmea_depth_test_large.xlsx",
  logs:
    "2024-01-15 14:30:22 WARN: Weight deviation detected\n2024-01-15 14:30:45 ERROR: 15 tablets out of spec\n2024-01-15 14:31:10 INFO: Production line 2 paused",
  reports:
    "Quality Control Report QC-2024-045: Tablet weight out of specification. Impact: 1500 tablets affected. Severity: Medium. Batch quarantined pending investigation.",
  process_data:
    "Compression force: 12kN (spec: 10kN). Tablet hardness: 8kP (spec: 6\u201310kP). Production rate: 5000 tablets/hour. Operator: ID-789. Shift: Day shift.",
  historical_capa:
    "Previous CAPA-2023-156 addressed similar weight issue. Root cause: Operator setup error. Corrective action: Enhanced training program implemented.",
};

export default function RCAIntakeForm({ onSubmit, loading }: Props) {
  const [draft, setDraft] = useState<RCAIntakeDraft>(createEmptyDraft);
  const [showOptional, setShowOptional] = useState(false);
  const [errors, setErrors] = useState<Partial<Record<keyof RCAIntakeDraft, string>>>({});

  useEffect(() => {
    setDraft(loadDraftFromStorage());
  }, []);

  const update = useCallback(
    (key: keyof RCAIntakeDraft, value: string) => {
      setDraft((prev) => {
        const next = { ...prev, [key]: value };
        saveDraftToStorage(next);
        return next;
      });
      if (errors[key]) setErrors((e) => ({ ...e, [key]: undefined }));
    },
    [errors],
  );

  function validate(): boolean {
    const next: typeof errors = {};
    if (!draft.complaint_id.trim()) next.complaint_id = "Complaint ID is required.";
    if (!draft.complaint.trim()) next.complaint = "Problem statement is required.";
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  function submit(method: "why" | "fishbone") {
    if (!validate()) return;
    const payload = buildPayloadFromDraft(draft);
    onSubmit({ ...payload, method }, method);
  }

  function clearDraft() {
    const empty = createEmptyDraft();
    setDraft(empty);
    saveDraftToStorage(empty);
    setErrors({});
  }

  function loadExample() {
    const next = { ...createEmptyDraft(), ...EXAMPLE_DRAFT };
    setDraft(next);
    saveDraftToStorage(next);
    setErrors({});
    setShowOptional(true);
  }

  const filledOptional = OPTIONAL_FIELDS.filter(
    (f) => draft[f.key]?.toString().trim(),
  ).length;

  return (
    <div className="w-full max-w-3xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <p className="text-xs font-mono uppercase tracking-widest text-muted mb-1">
          NOVINTIX · CAPA AI
        </p>
        <h1 className="text-3xl font-bold text-foreground leading-tight">
          Root Cause Analysis
        </h1>
        <p className="mt-2 text-muted text-sm max-w-lg">
          Fill in the complaint details below, then choose your analysis method.
          Your draft is saved automatically.
        </p>
        <button
          type="button"
          onClick={loadExample}
          disabled={loading}
          className="mt-3 text-xs rounded-lg border border-foreground/20 px-3 py-1.5 text-muted hover:text-foreground hover:border-foreground/40 transition-colors disabled:opacity-50"
        >
          &#x1F4CB; Load example
        </button>
      </div>

      <form onSubmit={(e) => e.preventDefault()} noValidate className="space-y-6">
        {/* Required section */}
        <section>
          <SectionHeader label="Core Information" required />
          <div className="space-y-4 mt-3">
            {REQUIRED_FIELDS.map((f) => (
              <Field
                key={f.key}
                def={f}
                value={draft[f.key] as string}
                onChange={(v) => update(f.key, v)}
                error={errors[f.key]}
              />
            ))}
          </div>
        </section>

        {/* Optional section */}
        <section>
          <button
            type="button"
            onClick={() => setShowOptional((s) => !s)}
            className="flex items-center gap-2 text-sm font-semibold text-accent hover:opacity-80 transition-opacity"
          >
            <span
              className={`inline-block transition-transform duration-200 ${showOptional ? "rotate-90" : ""}`}
            >
              ▶
            </span>
            Supporting Evidence &amp; Context
            {filledOptional > 0 && (
              <span className="ml-1 rounded-full bg-accent text-surface text-xs px-2 py-0.5">
                {filledOptional} filled
              </span>
            )}
          </button>

          {showOptional && (
            <div className="space-y-4 mt-4 border-l-2 border-accent/20 pl-4">
              {OPTIONAL_FIELDS.map((f) => (
                <Field
                  key={f.key}
                  def={f}
                  value={draft[f.key] as string}
                  onChange={(v) => update(f.key, v)}
                />
              ))}
            </div>
          )}
        </section>

        {/* Method selection & submit */}
        <section className="pt-2">
          <SectionHeader label="Choose Analysis Method" required />
          <p className="text-xs text-muted mb-4 mt-1">
            <strong>Why Analysis</strong> — iterative 5-Why drill-down, best when the causal
            chain is fairly linear.&nbsp;&nbsp;
            {" "}<strong>Fishbone (Ishikawa)</strong>{" \u2014 "}category-wide cause mapping across
            6M / 4P dimensions, best for multi-factor problems.
          </p>
          <div className="flex flex-wrap gap-3">
            <MethodButton
              label="Why Analysis"
              sub="Linear 5-Why drill-down"
              icon="🔍"
              onClick={() => submit("why")}
              disabled={loading}
            />
            <MethodButton
              label="Fishbone Analysis"
              sub="Multi-category Ishikawa"
              icon="🐟"
              onClick={() => submit("fishbone")}
              disabled={loading}
            />
          </div>
        </section>

        {/* Clear draft */}
        <div className="pt-1">
          <button
            type="button"
            onClick={clearDraft}
            disabled={loading}
            className="text-xs text-muted hover:text-danger transition-colors underline underline-offset-2"
          >
            Clear draft
          </button>
        </div>
      </form>
    </div>
  );
}

/* ── Sub-components ──────────────────────────────────────────────────── */

function SectionHeader({ label, required }: Readonly<{ label: string; required?: boolean }>) {
  return (
    <h2 className="text-xs font-mono uppercase tracking-widest text-muted flex items-center gap-1">
      {label}
      {required && <span className="text-danger">*</span>}
    </h2>
  );
}

function Field({
  def,
  value,
  onChange,
  error,
}: Readonly<{
  def: FieldDef;
  value: string;
  onChange: (v: string) => void;
  error?: string;
}>) {
  const inputClass = `w-full rounded-lg border px-3 py-2 text-sm font-sans bg-surface text-foreground
    placeholder:text-muted/50 focus:outline-none focus:ring-2 focus:ring-accent/50
    transition-shadow resize-y
    ${error ? "border-danger ring-1 ring-danger" : "border-foreground/15 hover:border-foreground/30"}`;

  return (
    <div>
      <label className="block text-sm font-medium text-foreground mb-1">
        {def.label}
        {def.required && <span className="text-danger ml-0.5">*</span>}
      </label>
      {(def.rows ?? 1) === 1 ? (
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={def.placeholder}
          className={inputClass}
        />
      ) : (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={def.placeholder}
          rows={def.rows}
          className={inputClass}
        />
      )}
      {def.hint && !error && (
        <p className="mt-1 text-xs text-muted">{def.hint}</p>
      )}
      {error && <p className="mt-1 text-xs text-danger">{error}</p>}
    </div>
  );
}

function MethodButton({
  label,
  sub,
  icon,
  onClick,
  disabled,
}: Readonly<{
  label: string;
  sub: string;
  icon: string;
  onClick: () => void;
  disabled: boolean;
}>) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="flex items-center gap-3 rounded-xl border-2 border-accent px-5 py-3 bg-surface
        hover:bg-surface-strong active:scale-95 transition-all disabled:opacity-50 disabled:cursor-not-allowed
        focus:outline-none focus:ring-2 focus:ring-accent/50 min-w-[190px]"
    >
      <span className="text-2xl leading-none">{icon}</span>
      <div className="text-left">
        <div className="text-sm font-bold text-foreground">{label}</div>
        <div className="text-xs text-muted">{sub}</div>
      </div>
    </button>
  );
}
