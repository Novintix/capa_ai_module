import pandas as pd
import json
import re
import io
from fastapi import UploadFile
import PyPDF2
from docx import Document
import os
from langchain_core.tools import tool

# Default metrics file path
DEFAULT_METRICS_PATH = os.path.join(os.path.dirname(__file__), "metrics.json")


# ─────────────────────────────────────────────────────────────
# FILE PARSING TOOLS
# @tool — explicitly called by router, NOT via LLM/ReAct
# ─────────────────────────────────────────────────────────────

@tool
def parse_json_file(content: bytes) -> str:
    """Parse a JSON file and return a pretty-printed JSON string."""
    data = json.loads(content)
    return json.dumps(data, indent=2)


@tool
def parse_csv_file(content: bytes) -> str:
    """Parse a CSV file and return a markdown table string."""
    df = pd.read_csv(io.BytesIO(content))
    return df.to_markdown(index=False)


@tool
def parse_excel_file(content: bytes) -> str:
    """Parse an Excel (.xlsx/.xls) file and return a markdown table string."""
    df = pd.read_excel(io.BytesIO(content))
    return df.to_markdown(index=False)


@tool
def parse_pdf_file(content: bytes) -> str:
    """Parse a PDF file and return extracted text."""
    pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() + "\n"
    return text


@tool
def parse_docx_file(content: bytes) -> str:
    """Parse a .docx Word file and return extracted paragraph text."""
    doc = Document(io.BytesIO(content))
    return "\n".join([para.text for para in doc.paragraphs])


@tool
def parse_txt_file(content: bytes) -> str:
    """Parse a plain text file and return its UTF-8 decoded content."""
    return content.decode("utf-8")


# ─────────────────────────────────────────────────────────────
# DISPATCHER — routes to the correct @tool based on filename
# Called by router.py; keeps FastAPI async compatibility
# ─────────────────────────────────────────────────────────────

class MetricsParser:
    # Maps file extension to the @tool function
    _TOOL_MAP = {
        ".json": parse_json_file,
        ".csv":  parse_csv_file,
        ".xlsx": parse_excel_file,
        ".xls":  parse_excel_file,
        ".pdf":  parse_pdf_file,
        ".docx": parse_docx_file,
        ".txt":  parse_txt_file,
    }

    @staticmethod
    async def parse_file(file: UploadFile) -> str:
        """
        Dispatcher: reads the uploaded file and routes to the correct @tool
        based on the file extension. Called explicitly — not via LLM/ReAct.
        """
        content = await file.read()
        filename = file.filename.lower()

        # TODO: Add Image OCR support if needed (requires Azure or Vision Model)
        if filename.endswith((".png", ".jpg", ".jpeg")):
            return f"[Image File Provided: {filename} - Content Extraction Not Implemented without OCR Service]"

        for ext, parse_tool in MetricsParser._TOOL_MAP.items():
            if filename.endswith(ext):
                try:
                    return parse_tool.invoke({"content": content})
                except Exception as e:
                    return f"Error parsing file {filename}: {str(e)}"

        return f"[Unsupported file format: {filename}]"


# ─────────────────────────────────────────────────────────────
# METRICS TOOLS
# @tool — explicitly called by nodes/router via .invoke(), NOT via LLM/ReAct
# ─────────────────────────────────────────────────────────────

@tool
def load_metrics(metrics_path: str = None) -> dict:
    """Load metrics definition from a JSON file. Falls back to default metrics.json."""
    path = metrics_path or DEFAULT_METRICS_PATH
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load metrics from {path}: {e}")
        return {}


@tool
def get_weights(metrics: dict = None) -> dict:
    """Extract parameter weights dict from a metrics definition. Loads default if metrics is None.
    Returns normalized weights that always sum to 1.0 for consistency."""
    resolved = load_metrics.invoke({}) if metrics is None else metrics
    
    # Get raw weights
    raw_weights = {
        code: param.get("weight", 0.1)  # Default weight if missing
        for code, param in resolved.get("parameters", {}).items()
    }
    
    # Ensure all 10 parameters exist with default weights
    default_weights = {
        "HF": 0.18, "TR": 0.12, "PS": 0.10, "PC": 0.12, "DM": 0.10,
        "SY": 0.12, "OE": 0.08, "CA": 0.08, "SU": 0.05, "AU": 0.05
    }
    
    # Merge with defaults
    final_weights = {**default_weights, **raw_weights}
    
    # Normalize to sum to 1.0 for consistency
    total = sum(final_weights.values())
    if total > 0:
        final_weights = {k: v/total for k, v in final_weights.items()}
    
    return final_weights


# ─────────────────────────────────────────────────────────────
# UTILITY FUNCTIONS (non-tool — internal graph helpers)
# ─────────────────────────────────────────────────────────────

def build_evidence_summary(similar_cases: list, param_factor_keys: dict, pattern_data=None) -> dict:
    """
    Builds a deterministic evidence string per parameter using pattern data
    and similar cases. Now fully dynamic - works with ANY parameter set.
    """
    sorted_cases = sorted(
        similar_cases,
        key=lambda c: float(c.get("similarity_score", c.get("similarity", 0))),
        reverse=True
    )

    evidence = {}
    for code, factor_key in param_factor_keys.items():
        evidence_parts = []
        
        # Add pattern-specific evidence first (higher priority) - DYNAMIC
        if pattern_data:
            # Generic pattern evidence that works for any parameter
            if "trend" in factor_key.lower() or "pattern" in factor_key.lower() or code.upper() in ["TR", "TREND"]:
                # Trend-related parameters
                if hasattr(pattern_data, 'trend_category') and pattern_data.trend_category:
                    trend_cat = pattern_data.trend_category
                    if "uncontrolled exponential" in trend_cat.lower():
                        evidence_parts.append("TREND: Uncontrolled exponential trend (score 10)")
                    elif "exponential" in trend_cat.lower():
                        evidence_parts.append("TREND: Exponential trend (score 9)")
                    elif "increasing" in trend_cat.lower():
                        evidence_parts.append("TREND: Increasing trend (score 8)")
                    else:
                        trend_score = getattr(pattern_data, 'trend_score', 5)
                        evidence_parts.append(f"TREND: {trend_cat} (score {trend_score})")
            
            elif "frequency" in factor_key.lower() or "historical" in factor_key.lower() or code.upper() in ["HF", "FREQ"]:
                # Frequency-related parameters
                matched_ids = getattr(pattern_data, 'matched_complaint_ids', [])
                count = len(matched_ids) if matched_ids else 0
                if count >= 10:
                    evidence_parts.append(f"FREQUENCY: {count} historical cases (high frequency, score 8-9)")
                elif count >= 5:
                    evidence_parts.append(f"FREQUENCY: {count} historical cases (medium frequency, score 5-6)")
                elif count >= 2:
                    evidence_parts.append(f"FREQUENCY: {count} historical cases (low frequency, score 3-4)")
                else:
                    evidence_parts.append(f"FREQUENCY: {count} historical cases (rare, score 1-2)")
            
            elif "systemic" in factor_key.lower() or "scope" in factor_key.lower() or code.upper() in ["SY", "SCOPE", "IMPACT"]:
                # Systemic/scope-related parameters
                pattern_text = getattr(pattern_data, 'identified_pattern', "")
                matched_ids = getattr(pattern_data, 'matched_complaint_ids', [])
                if "across" in pattern_text.lower() and ("site" in pattern_text.lower() or "region" in pattern_text.lower()):
                    evidence_parts.append("SYSTEMIC: Multi-site/region pattern (score 7-8)")
                elif len(matched_ids) > 5:
                    evidence_parts.append("SYSTEMIC: Multiple cases pattern (score 6-7)")
                else:
                    evidence_parts.append("SYSTEMIC: Limited scope pattern (score 3-4)")
            
            elif "risk" in factor_key.lower() or "probability" in factor_key.lower() or code.upper() in ["RISK", "PROB"]:
                # Risk/probability-related parameters
                confidence = getattr(pattern_data, 'confidence', 0.5)
                if confidence >= 0.9:
                    evidence_parts.append(f"RISK: High confidence pattern ({confidence:.1%}, score 8-9)")
                elif confidence >= 0.7:
                    evidence_parts.append(f"RISK: Medium confidence pattern ({confidence:.1%}, score 5-6)")
                else:
                    evidence_parts.append(f"RISK: Low confidence pattern ({confidence:.1%}, score 2-3)")

        # Add similar cases evidence - DYNAMIC extraction
        for case in sorted_cases[:1]:  # Only use highest similarity case for consistency
            val = case.get("occurrence_factors", {}).get(factor_key, "").strip()
            if not val:
                # Try generic field mappings that work for any parameter type
                if "frequency" in factor_key.lower() and case.get("repeated"):
                    val = "REPEATED: Issue marked as repeated (score 6-7)"
                elif "control" in factor_key.lower() and case.get("capa_needed"):
                    val = f"CONTROLS: CAPA required - {case.get('capa_rationale', 'controls ineffective')} (score 6-8)"
                elif "detection" in factor_key.lower() and case.get("days_open"):
                    days = case.get("days_open", 0)
                    if days > 90:
                        val = f"DETECTION: {days} days open (poor detection, score 7-8)"
                    elif days > 30:
                        val = f"DETECTION: {days} days open (moderate detection, score 5-6)"
                    else:
                        val = f"DETECTION: {days} days open (good detection, score 2-3)"
                elif ("systemic" in factor_key.lower() or "scope" in factor_key.lower()) and case.get("site"):
                    val = f"SCOPE: Affects site {case.get('site')} (score 4-5)"
                elif "severity" in factor_key.lower() and case.get("severity"):
                    severity = case.get("severity", "").lower()
                    if "critical" in severity:
                        val = f"SEVERITY: Critical level (score 8-9)"
                    elif "high" in severity:
                        val = f"SEVERITY: High level (score 6-7)"
                    elif "medium" in severity:
                        val = f"SEVERITY: Medium level (score 4-5)"
                    else:
                        val = f"SEVERITY: {case.get('severity')} level (score 2-3)"
            
            if val:
                case_id = case.get("case_id", case.get("complaint_id", case.get("complaintId", "?")))
                sim = case.get("similarity_score", case.get("similarity", "?"))
                # Clean and standardize evidence text
                val_clean = re.sub(r'[^\w\s\.\,\-\:\(\)]', '', str(val))
                val_clean = re.sub(r'\s+', ' ', val_clean).strip()
                evidence_parts.append(f"CASE {case_id} (sim {sim}): {val_clean}")
                break  # Only use first matching case for determinism
        
        # Combine all evidence parts - DETERMINISTIC order
        if evidence_parts:
            evidence[code] = " | ".join(evidence_parts)
        else:
            evidence[code] = "NO EVIDENCE: Default score 1"

    return evidence


def build_prompt(description: str, product: str, date: str,
                 context: str,
                 metrics: dict = None,
                 evidence_summary: dict = None) -> str:
    """
    Build the full scoring prompt dynamically from the metrics definition.
    If evidence_summary is provided, injects pre-computed per-parameter evidence.
    """
    if metrics is None:
        metrics = load_metrics.invoke({})

    parameters = metrics.get("parameters", {})

    param_guide = ""
    weights_block = "| Code | Parameter | Weight |\n|------|-----------|--------|\n"

    for code, param in parameters.items():
        name = param["name"]
        weight = param["weight"]
        levels = param["levels"]

        param_guide += f"\n#### {code} - {name} (Weight: {int(weight * 100)}%)\n"
        for score, desc in sorted(levels.items(), key=lambda x: int(x[0])):
            param_guide += f"{score} -> {desc}\n"

        weights_block += f"| {code} | {name} | {int(weight * 100)}% |\n"

    evidence_block = ""
    if evidence_summary:
        evidence_block = "\n### PRE-COMPUTED EVIDENCE FROM SIMILAR CASES\n"
        evidence_block += "The evidence below is already merged from all similar cases. Use it directly — do NOT re-average or re-interpret.\n\n"
        for code, evidence_text in evidence_summary.items():
            evidence_block += f"- **{code}**: {evidence_text}\n"

    from Agents.occurrence.prompts import OCCURRENCE_PROMPT_TEMPLATE

    return OCCURRENCE_PROMPT_TEMPLATE.format(
        description=description,
        product=product,
        date=date,
        context=context,
        param_guide=param_guide,
        weights_block=weights_block,
        evidence_block=evidence_block
    )
