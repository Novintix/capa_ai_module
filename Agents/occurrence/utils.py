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
    """Extract parameter weights dict from a metrics definition. Loads default if metrics is None."""
    resolved = load_metrics.invoke({}) if metrics is None else metrics
    return {
        code: param["weight"]
        for code, param in resolved.get("parameters", {}).items()
    }


# ─────────────────────────────────────────────────────────────
# UTILITY FUNCTIONS (non-tool — internal graph helpers)
# ─────────────────────────────────────────────────────────────

def build_evidence_summary(similar_cases: list, param_factor_keys: dict) -> dict:
    """
    Builds a deterministic evidence string per parameter using only the
    highest-similarity case. This ensures the LLM receives exactly one
    evidence string per parameter — no conflict, no random selection.
    """
    sorted_cases = sorted(
        similar_cases,
        key=lambda c: float(c.get("similarity_score", 0)),
        reverse=True
    )

    evidence = {}
    for code, factor_key in param_factor_keys.items():
        found = False
        for case in sorted_cases:
            val = case.get("occurrence_factors", {}).get(factor_key, "").strip()
            if val:
                case_id = case.get("case_id", "?")
                sim = case.get("similarity_score", "?")
                # Aggressive sanitization: remove ALL special characters that could break JSON
                # Keep only alphanumeric, spaces, basic punctuation
                val_sanitized = re.sub(r'[^\w\s\.\,-]', '', val)
                # Replace multiple whitespace with single space
                val_sanitized = re.sub(r'\s+', ' ', val_sanitized).strip()
                evidence[code] = f"{case_id} (similarity {sim}): {val_sanitized}"
                found = True
                break
        if not found:
            evidence[code] = "No historical evidence available."

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
