"""
FMEA reader utilities for Loop Control.

Supports filename-only input by resolving relative paths under Agents/loop_control.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


DEFAULT_FMEA_FILENAME = "fmea_depth_test_large.xlsx"
LOOP_CONTROL_DIR = Path(__file__).resolve().parents[1]


def resolve_fmea_path(fmea_document_path: str | None) -> Path:
    """
    Resolve FMEA path with loop_control directory as default base.

    Rules:
    - None or empty -> Agents/loop_control/fmea_depth_test_large.xlsx
    - Absolute path -> used as-is
    - Relative filename/path -> resolved under Agents/loop_control
    """
    raw = (fmea_document_path or "").strip()
    if not raw:
        candidate = LOOP_CONTROL_DIR / DEFAULT_FMEA_FILENAME
    else:
        provided = Path(raw)
        candidate = provided if provided.is_absolute() else (LOOP_CONTROL_DIR / provided)

    if not candidate.exists() or not candidate.is_file():
        raise FileNotFoundError(f"FMEA file not found: {candidate}")

    return candidate


def load_fmea_lookup_texts(fmea_document_path: str | None) -> list[str]:
    """
    Load text entries from FMEA for cause lookup.

    Prefer failure-mode/cause columns; fallback to row text join.
    """
    fmea_path = resolve_fmea_path(fmea_document_path)
    workbook = pd.read_excel(fmea_path, sheet_name=None)

    lookup_texts: list[str] = []

    for _, df in workbook.items():
        if df is None or df.empty:
            continue

        normalized_columns = {
            col: str(col).strip().lower().replace(" ", "_")
            for col in df.columns
        }
        df = df.rename(columns=normalized_columns)

        preferred = [
            col for col in df.columns
            if any(token in col for token in ("failure_mode", "failure", "cause", "potential_cause"))
        ]

        if preferred:
            for col in preferred:
                values = df[col].dropna().astype(str).str.strip()
                lookup_texts.extend([v for v in values if v])
            continue

        # Fallback for unknown column layouts.
        for _, row in df.iterrows():
            parts = [str(v).strip() for v in row.values.tolist() if pd.notna(v) and str(v).strip()]
            if parts:
                lookup_texts.append(" | ".join(parts[:4]))

    # Preserve order while de-duplicating.
    unique_texts = list(dict.fromkeys(lookup_texts))
    return unique_texts
