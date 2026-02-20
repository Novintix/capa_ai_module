import pandas as pd
import json
import io
from fastapi import UploadFile
import PyPDF2
from docx import Document
import os

# Default metrics file path
DEFAULT_METRICS_PATH = os.path.join(os.path.dirname(__file__), "metrics.json")

class MetricsParser:
    @staticmethod
    async def parse_file(file: UploadFile) -> str:
        """
        Parses text/data from an uploaded file (JSON, Excel, CSV, PDF, Docx).
        Returns a string representation of the data.
        """
        content = await file.read()
        filename = file.filename.lower()
        
        try:
            if filename.endswith(".json"):
                data = json.loads(content)
                return json.dumps(data, indent=2)
                
            elif filename.endswith(".csv"):
                df = pd.read_csv(io.BytesIO(content))
                return df.to_markdown(index=False)
                
            elif filename.endswith(".xlsx") or filename.endswith(".xls"):
                df = pd.read_excel(io.BytesIO(content))
                return df.to_markdown(index=False)
                
            elif filename.endswith(".pdf"):
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                return text
                
            elif filename.endswith(".docx"):
                doc = Document(io.BytesIO(content))
                text = "\n".join([para.text for para in doc.paragraphs])
                return text
                
            elif filename.endswith(".txt"):
                return content.decode("utf-8")
                
            # TODO: Add Image OCR support if needed (requires Azure or Vision Model)
            elif filename.endswith((".png", ".jpg", ".jpeg")):
                return f"[Image File Provided: {filename} - Content Extraction Not Implemented without OCR Service]"
                
            else:
                return f"[Unsupported file format: {filename}]"
                
        except Exception as e:
            return f"Error parsing file {filename}: {str(e)}"


def load_metrics(metrics_path: str = None) -> dict:
    """Load metrics from a JSON file. Falls back to default metrics.json."""
    path = metrics_path or DEFAULT_METRICS_PATH
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        # Fallback to empty if default file missing (though it should be there)
        print(f"Warning: Could not load metrics from {path}: {e}")
        return {}


def get_weights(metrics: dict = None) -> dict:
    """Extract weights dict from metrics definition."""
    if metrics is None:
        metrics = load_metrics()
    return {
        code: param["weight"]
        for code, param in metrics.get("parameters", {}).items()
    }


def build_evidence_summary(similar_cases: list, param_factor_keys: dict) -> dict:
    """
    Builds a deterministic evidence string per parameter using only the
    highest-similarity case. This ensures the LLM receives exactly one
    evidence string per parameter — no conflict, no random selection.
    """
    # Sort cases by similarity_score descending — highest similarity first
    sorted_cases = sorted(
        similar_cases,
        key=lambda c: float(c.get("similarity_score", 0)),
        reverse=True
    )

    evidence = {}
    for code, factor_key in param_factor_keys.items():
        # Find the first (highest-similarity) case that has this factor
        found = False
        for case in sorted_cases:
            val = case.get("occurrence_factors", {}).get(factor_key, "").strip()
            if val:
                case_id = case.get("case_id", "?")
                sim = case.get("similarity_score", "?")
                evidence[code] = f"{case_id} (similarity {sim}): {val}"
                found = True
                break
        if not found:
            evidence[code] = "No historical evidence available."

    return evidence



def build_prompt(description: str, product: str, date: str,
                 similar_cases: str, context: str,
                 metrics: dict = None,
                 evidence_summary: dict = None) -> str:
    """
    Build the full scoring prompt dynamically from the metrics definition.
    If evidence_summary is provided, injects pre-computed per-parameter evidence.
    """
    if metrics is None:
        metrics = load_metrics()

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

    # Build pre-computed evidence block
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
        similar_cases=similar_cases,
        context=context,
        param_guide=param_guide,
        weights_block=weights_block,
        evidence_block=evidence_block
    )

