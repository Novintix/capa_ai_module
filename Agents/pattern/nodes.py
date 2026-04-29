import json
import re
import logging
from typing import List, Dict, Optional
from .state import AgentState
from .prompt import (
    PATTERN_ANALYSIS_SYSTEM_PROMPT,
    PATTERN_ANALYSIS_USER_PROMPT_TEMPLATE
)
from .logger import log_node_entry, log_node_exit, log_routing_decision, log_error
from .tools.mongo_tool import fetch_similar_complaints, detect_failure_class
from config.aws_bedrock_config import get_llm

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Company standard trend score → category map
# DO NOT MODIFY — these are the official company definitions
# ─────────────────────────────────────────────────────────────
SCORE_TO_CATEGORY = {
    1:  "No trend; stable flat data",
    2:  "Minor fluctuation but no upward trend",
    3:  "One short-term spike, not repeated",
    4:  "Weak increasing tendency",
    5:  "Small but noticeable trend signal",
    6:  "Clear visible upward trend",
    7:  "Strong accelerating trend",
    8:  "Recurring trend peaks",
    9:  "Persistent accelerating trend",
    10: "Uncontrolled exponential trend",
}

# Reverse map — used to validate LLM's category text
CATEGORY_TO_SCORE = {v: k for k, v in SCORE_TO_CATEGORY.items()}

ID_FIELD_ALIASES = [
    "complaint_id", "NC_ID", "nc_id",
    "record_id", "issue_id", "ticket_id", "case_id"
]


# ─────────────────────────────────────────────────────────────
# Formatting helpers
# ─────────────────────────────────────────────────────────────

def flatten_record(record: Dict) -> str:
    skip_keys = {"_id"}
    parts = []
    for key, value in record.items():
        if key in skip_keys:
            continue
        if value in (None, "", [], {}):
            continue
        readable_key = key.replace("_", " ").replace("-", " ").title()
        parts.append(f"{readable_key}: {value}")
    return " | ".join(parts)


def format_historical_data(complaints: List[Dict]) -> str:
    if not complaints:
        return "No historical complaints found."
    lines = [f"Total historical records retrieved: {len(complaints)}\n"]
    for i, record in enumerate(complaints, 1):
        lines.append(f"[Record {i}]\n  {flatten_record(record)}")
    return "\n".join(lines)


def clean_llm_response(response_text: str) -> str:
    if "<reasoning>" in response_text and "</reasoning>" in response_text:
        response_text = re.sub(
            r'<reasoning>.*?</reasoning>\s*',
            '', response_text, flags=re.DOTALL
        ).strip()
    response_text = response_text.replace('```json', '').replace('```', '').strip()
    start_idx = response_text.find('{')
    end_idx = response_text.rfind('}')
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        response_text = response_text[start_idx:end_idx + 1]
    return response_text


# ─────────────────────────────────────────────────────────────
# Post-processing validation helpers
# ─────────────────────────────────────────────────────────────

def extract_ids_from_historical(historical_complaints: List[Dict]) -> List[str]:
    ids = []
    for doc in historical_complaints:
        for field in ID_FIELD_ALIASES:
            val = doc.get(field)
            if val and str(val).strip():
                ids.append(str(val).strip())
                break
    return ids


def extract_ids_from_explanation(explanation: str) -> List[str]:
    """Extract IDs mentioned in explanation text as fallback."""
    if not explanation:
        return []
    pattern = r'\b([A-Z]{1,6}-\d{2,6}(?:-\d+)?)\b'
    found = re.findall(pattern, explanation)
    return list(dict.fromkeys(found))


def calculate_confidence(
    matched_ids: List[str],
    historical_complaints: List[Dict]
) -> float:
    """
    Calculate confidence using the formula in code.
    Never relies on LLM's confidence value.
    """
    matched_set = set(matched_ids)

    matched_docs = []
    for doc in historical_complaints:
        for field in ID_FIELD_ALIASES:
            val = doc.get(field)
            if val and str(val).strip() in matched_set:
                matched_docs.append(doc)
                break

    repeated_count = 0
    dual_reportable_count = 0
    regions = set()
    sites = set()

    for doc in matched_docs:
        for repeat_field in ["Repeated_NotRepeated", "repeated_not_repeated", "Repeated", "repeated"]:
            val = str(doc.get(repeat_field, "")).lower()
            if "repeat" in val and "not" not in val:
                repeated_count += 1
                break

        fda_fields = ["FDA_Reportable", "fda_reportable", "FDA"]
        eu_fields  = ["EU_Reportable",  "eu_reportable",  "EU"]
        fda_val = str(doc.get(next((f for f in fda_fields if f in doc), ""), "")).lower()
        eu_val  = str(doc.get(next((f for f in eu_fields  if f in doc), ""), "")).lower()
        if fda_val in ("yes", "true", "1") and eu_val in ("yes", "true", "1"):
            dual_reportable_count += 1

        for rf in ["Region_Country", "region_country", "Region", "region", "country"]:
            val = doc.get(rf)
            if val:
                regions.add(str(val).strip())
                break

        for sf in ["Site", "site", "facility", "plant"]:
            val = doc.get(sf)
            if val:
                sites.add(str(val).strip())
                break

    confidence = 0.50
    confidence += 0.05 * len(matched_ids)
    confidence += 0.03 * repeated_count
    confidence += 0.03 * dual_reportable_count
    if len(regions) >= 3:
        confidence += 0.05
    if len(sites) >= 3:
        confidence += 0.05

    return round(min(confidence, 0.97), 2)


def derive_trend_score(matched_count: int) -> int:
    """Derive score from matched count using company standard mapping."""
    if matched_count == 0:   return 1
    elif matched_count == 1: return 3
    elif matched_count <= 3: return 4
    elif matched_count <= 4: return 5
    elif matched_count <= 5: return 6
    elif matched_count <= 6: return 7
    elif matched_count <= 8: return 8
    elif matched_count <= 9: return 9
    else:                    return 10


def validate_and_fix_result(
    result: Dict,
    historical_complaints: List[Dict],
    failure_class: str,
    current_product: Optional[str] = None,
    current_region: Optional[str] = None,
) -> Dict:
    """
    Post-processing validation.
    Fixes missing/incorrect fields using code logic.
    Enforces company standard category text.
    """

    # ── Fix 1: matched_complaint_ids ──────────────────────────
    matched_ids = result.get("matched_complaint_ids", [])

    if not matched_ids:
        explanation = result.get("explanation", "")
        matched_ids = extract_ids_from_explanation(explanation)
        logger.warning(f"[Validate] Extracted {len(matched_ids)} IDs from explanation: {matched_ids}")

    if not matched_ids:
        matched_ids = extract_ids_from_historical(historical_complaints)
        logger.warning(f"[Validate] Fallback to all fetched IDs: {matched_ids}")

    result["matched_complaint_ids"] = matched_ids

    # ── Fix 2: confidence — always recalculate in code ────────
    result["confidence"] = calculate_confidence(matched_ids, historical_complaints)
    logger.info(f"[Validate] Recalculated confidence: {result['confidence']}")

    # ── Fix 3: trend_score — derive from matched count ────────
    llm_score      = result.get("trend_score")
    expected_score = derive_trend_score(len(matched_ids))

    if not llm_score or abs(llm_score - expected_score) > 1:
        logger.warning(
            f"[Validate] trend_score mismatch — "
            f"LLM={llm_score}, expected={expected_score} — using expected"
        )
        result["trend_score"] = expected_score

    # ── Fix 4: trend_category — MUST match company standard ───
    # If LLM returned a non-standard text → override with official text
    llm_category = result.get("trend_category", "")
    if llm_category not in CATEGORY_TO_SCORE:
        # LLM returned non-standard text — derive from score
        result["trend_category"] = SCORE_TO_CATEGORY.get(
            result["trend_score"],
            "No trend; stable flat data"
        )
        logger.warning(
            f"[Validate] Non-standard trend_category '{llm_category}' — "
            f"replaced with: '{result['trend_category']}'"
        )
    else:
        # LLM category is valid — but sync score to match it
        result["trend_score"] = CATEGORY_TO_SCORE[llm_category]

    # ── Fix 5: identified_pattern ─────────────────────────────
    if not result.get("identified_pattern"):
        matched_set = set(matched_ids)
        regions, sites, products = set(), set(), set()

        # Seed with current complaint's own context
        if current_product:
            products.add(current_product.strip())
        if current_region:
            regions.add(current_region.strip())

        for doc in historical_complaints:
            for field in ID_FIELD_ALIASES:
                val = doc.get(field)
                if val and str(val).strip() in matched_set:
                    for rf in ["Region_Country", "region_country", "Region", "region"]:
                        if doc.get(rf): regions.add(str(doc[rf]).strip()); break
                    for sf in ["Site", "site", "facility"]:
                        if doc.get(sf): sites.add(str(doc[sf]).strip()); break
                    for pf in ["Product_Family", "product_family", "product", "Product"]:
                        if doc.get(pf): products.add(str(doc[pf]).strip()); break
                    break

        product_str = ", ".join(sorted(products)) if products else "Unknown Product"
        site_str    = ", ".join(sorted(sites))    if sites    else "multiple sites"
        region_str  = f"{len(regions)} regions"   if regions  else "multiple regions"

        result["identified_pattern"] = (
            f"Recurring {failure_class} in {product_str} "
            f"across {site_str} and {region_str}"
        )
        logger.warning(f"[Validate] Built identified_pattern: {result['identified_pattern']}")

    logger.info(
        f"[Validate] Final — score={result['trend_score']} "
        f"category='{result['trend_category']}' "
        f"confidence={result['confidence']} "
        f"matched_ids={result['matched_complaint_ids']}"
    )

    return result


# ─────────────────────────────────────────────────────────────
# NODES
# ─────────────────────────────────────────────────────────────

def initialize_state_node(state: AgentState) -> AgentState:
    log_node_entry("initialize", state)

    description   = state.get("complaint_description", "")
    failure_class = detect_failure_class(description) or "Unclassified"

    logger.info(f"[Initialize] complaint_id={state.get('complaint_id')} failure_class={failure_class}")

    updates = {
        "iteration": 0,
        "max_iterations": 3,
        "historical_complaints": [],
        "failure_class": failure_class,
        "trend_score": None,
        "trend_category": None,
        "confidence": None,
        "explanation": None,
        "matched_complaint_ids": [],
        "identified_pattern": None,
        "error": None,
        "next_step": "fetch_data"
    }

    log_node_exit("initialize", updates)
    return updates


def fetch_historical_data_node(state: AgentState) -> AgentState:
    log_node_entry("fetch_data", state)

    try:
        historical_data = fetch_similar_complaints(
            description=state["complaint_description"],
            current_id=state["complaint_id"],
            failure_class=state.get("failure_class"),
            company_schema=state.get("company_schema"),
        )

        fetched_ids = []
        for doc in historical_data:
            for id_field in ID_FIELD_ALIASES:
                if doc.get(id_field):
                    fetched_ids.append(doc[id_field])
                    break

        logger.info(f"[FetchData] Retrieved {len(historical_data)} records — IDs: {fetched_ids}")

        updates = {
            "historical_complaints": historical_data,
            "next_step": "analyze_trend"
        }

        log_routing_decision("fetch_data", "analyze_trend", f"Found {len(historical_data)} records")
        log_node_exit("fetch_data", {"count": len(historical_data)})
        return updates

    except Exception as e:
        error_msg = f"Data fetch failed: {str(e)}"
        log_error("fetch_data", error_msg)
        return {
            "error": error_msg,
            "historical_complaints": [],
            "next_step": "analyze_trend"
        }


def analyze_trend_node(state: AgentState) -> AgentState:
    log_node_entry("analyze_trend", state)

    max_retries = 3
    current_attempt = 0
    last_error = None

    try:
        llm = get_llm()

        h_data        = state.get("historical_complaints", [])
        failure_class = state.get("failure_class", "Unclassified")
        data_text     = format_historical_data(h_data)

        logger.info(f"[AnalyzeTrend] Sending {len(h_data)} records to LLM — failure_class='{failure_class}'")

        user_prompt = PATTERN_ANALYSIS_USER_PROMPT_TEMPLATE.format(
            complaint_id=state["complaint_id"],
            complaint_description=state["complaint_description"],
            failure_class=failure_class,
            product=state.get("product_family") or "Unknown",
            region=state.get("region")         or "Unknown",
            severity=state.get("severity")     or "Unknown",
            historical_data_text=data_text,
            total_records=len(h_data),
        )

        full_prompt = PATTERN_ANALYSIS_SYSTEM_PROMPT + "\n\n" + user_prompt

        while current_attempt < max_retries:
            try:
                response = llm.invoke(full_prompt)
                response_text = clean_llm_response(response.content)
                result = json.loads(response_text)

                logger.info(
                    f"[AnalyzeTrend] Raw LLM — score={result.get('trend_score')} "
                    f"category='{result.get('trend_category')}' "
                    f"matched_ids={result.get('matched_complaint_ids')}"
                )

                # Post-processing — enforces company standards in code
                result = validate_and_fix_result(
                    result, h_data, failure_class,
                    current_product=state.get("product_family"),
                    current_region=state.get("region"),
                )

                updates = {
                    "trend_score":           result.get("trend_score"),
                    "trend_category":        result.get("trend_category"),
                    "confidence":            result.get("confidence"),
                    "explanation":           result.get("explanation"),
                    "matched_complaint_ids": result.get("matched_complaint_ids", []),
                    "identified_pattern":    result.get("identified_pattern"),
                    "next_step": "finalize"
                }

                log_node_exit("analyze_trend", {k: v for k, v in updates.items() if k != "explanation"})
                return updates

            except Exception as e:
                current_attempt += 1
                last_error = str(e)
                log_error("analyze_trend", f"Attempt {current_attempt} failed: {last_error}")

        raise Exception(f"All {max_retries} attempts failed. Last: {last_error}")

    except Exception as e:
        error_msg = f"Trend analysis failed: {str(e)}"
        log_error("analyze_trend", error_msg)
        return {
            "error": error_msg,
            "trend_score": 1,
            "trend_category": "No trend; stable flat data",
            "explanation": f"Analysis failed: {str(e)}",
            "matched_complaint_ids": [],
            "identified_pattern": None,
            "next_step": "finalize"
        }


def finalize_node(state: AgentState) -> AgentState:
    log_node_entry("finalize", state)
    updates = {
        "iteration": state["iteration"] + 1,
        "next_step": "end"
    }
    log_routing_decision("finalize", "END", "Process complete")
    log_node_exit("finalize", updates)
    return updates