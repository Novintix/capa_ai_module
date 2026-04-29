"""
MongoDB fetch tool for Pattern Agent.

Two complementary search layers run in parallel and results are merged:

  Layer 1 — Structured fields (type, category, region)
              Catches complaints classified the same way regardless of wording.
              Fast, deterministic, no ML needed.

  Layer 2 — Vector similarity (semantic search)
              Catches the same problem described in different words.
              Handles all natural language variation.

Merged results (union, deduplicated) are passed to the LLM which decides
which records actually form a recurring pattern.

Collection: capa_complaints
"""

import os
import re
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from config.mongodb_config import get_capa_complaints_collection

HISTORY_MONTHS = int(os.getenv("PATTERN_HISTORY_MONTHS", "63"))

logger = logging.getLogger(__name__)

# ── Embedding model — lazy singleton ──────────────────────────────────────────
_model = None

def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        model_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        logger.info(f"[PatternTool] Loading embedding model: {model_name}")
        _model = SentenceTransformer(model_name)
        logger.info("[PatternTool] Embedding model ready")
    return _model


# ── Failure class detection (provides LLM context label) ─────────────────────

FAILURE_CLASS_TRIGGERS = {
    "Software/Firmware Failure": [
        "firmware", "software", "reboot", "watchdog", "lockout",
        "calculation", "dosage", "miscalculation", "interruption",
        "overcurrent", "overheating", "alarm", "connectivity",
        "display", "keypad", "sensor", "over-infusion", "underdose",
        "overdose", "therapy shutdown", "infusion stop", "discrepancy",
    ],
    "Electrical Failure": [
        "power", "electrical", "voltage", "current", "battery",
        "short circuit", "power failure", "power loss", "surge",
    ],
    "Seal Integrity Failure": [
        "seal", "sterility", "packaging", "burst", "rupture",
        "sterilization", "breach", "pouch", "integrity", "leakage", "leak",
    ],
    "Structural Failure": [
        "fracture", "crack", "cracking", "fatigue", "bending",
        "deformation", "strut", "porosity", "micro-fracture", "loosening",
    ],
    "Mechanical Failure": [
        "stiffness", "binding", "separation", "torque", "clamp",
        "handle", "hinge", "expansion", "motor", "roller", "mechanism",
    ],
    "Surface Defect": [
        "abrasion", "scratch", "pitting", "roughness", "coating",
        "corrosion", "machining mark", "burr", "anodizing", "passivation",
    ],
    "Calibration Drift": [
        "calibration", "drift", "flow rate", "deviation", "accuracy",
        "threshold", "tolerance", "frequency", "transducer",
    ],
    "Reagent Instability": [
        "reagent", "assay", "sensitivity", "false negative", "false positive",
        "lot-to-lot", "stability", "contamination", "signal decay",
    ],
    "Labeling Defect": [
        "label", "barcode", "expiry", "lot number", "marking",
        "traceability", "udi", "print",
    ],
    "Dimensional Non-conformance": [
        "dimensional", "tolerance", "geometry", "variance",
        "mismatch", "alignment", "porosity",
    ],
}


def detect_failure_class(description: str) -> Optional[str]:
    desc_lower = description.lower()
    for class_name, triggers in FAILURE_CLASS_TRIGGERS.items():
        if any(trigger in desc_lower for trigger in triggers):
            return class_name
    return None


# ── Field normalisation ───────────────────────────────────────────────────────

ID_FIELD_ALIASES = [
    "complaintId", "complaint_id", "NC_ID", "nc_id",
    "record_id", "issue_id", "ticket_id", "case_id",
]


def normalize_document(doc: Dict) -> Dict:
    if "_id" in doc:
        doc["_id"]          = str(doc["_id"])
        doc["complaint_id"] = doc["_id"]

    if "description" in doc:
        doc["Description_of_issue"] = doc["description"]

    if "productIdentifier" in doc:
        doc["Product_Family"] = doc["productIdentifier"]

    if "region" in doc:
        doc["Region_Country"] = doc["region"]
    elif "marketCountry" in doc:
        doc["Region_Country"] = doc["marketCountry"]

    if "site" in doc:
        doc["Site"] = doc["site"]

    if "fdaReportable" in doc:
        doc["FDA_Reportable"] = doc["fdaReportable"]
    if "euReportable" in doc:
        doc["EU_Reportable"] = doc["euReportable"]

    if "repeated" in doc:
        doc["Repeated_NotRepeated"] = "Repeated" if doc["repeated"] else "Not Repeated"

    doc.pop("descriptionEmbedding", None)
    return doc


# ── Layer 1 — Structured field search ────────────────────────────────────────

def _time_window_filter() -> Dict:
    """Returns a MongoDB filter for the last HISTORY_MONTHS months."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=HISTORY_MONTHS * 30)
    cutoff_str = cutoff.strftime("%Y-%m-%d")
    return {
        "$or": [
            {"raisedDate": {"$gte": cutoff_str}},
            {"createdAt":  {"$gte": cutoff}},
        ]
    }


def _fetch_by_structured_fields(
    collection,
    current_id: str,
    current_type: str,
    current_category: str,
    current_region: str,
    limit: int,
) -> List[Dict]:
    """
    Queries type, category, and region fields within the last HISTORY_MONTHS.
    Results sorted by raisedDate descending — most recent first.
    """
    or_clauses = []

    if current_type:
        or_clauses.append({"type": {"$regex": re.escape(current_type), "$options": "i"}})

    if current_category:
        or_clauses.append({"category": {"$regex": re.escape(current_category), "$options": "i"}})

    # Same region + same type — strongest regional pattern signal
    if current_region and current_type:
        or_clauses.append({
            "region": {"$regex": re.escape(current_region), "$options": "i"},
            "type":   {"$regex": re.escape(current_type),   "$options": "i"},
        })

    if not or_clauses:
        return []

    query = {
        "_id":  {"$ne": current_id},
        "$and": [
            {"$or": or_clauses},
            _time_window_filter(),
        ],
    }
    results = list(
        collection.find(query)
        .sort("raisedDate", -1)
        .limit(limit)
    )
    logger.info(
        f"[PatternTool] Structured search: {len(results)} records in last {HISTORY_MONTHS}m "
        f"(type='{current_type}' category='{current_category}' region='{current_region}')"
    )
    return results


# ── Layer 2 — Vector similarity search ───────────────────────────────────────

def _fetch_by_vector(
    collection,
    description: str,
    current_id: str,
    limit: int,
    threshold: float = 0.35,
) -> List[Dict]:
    """
    Semantic search on the description embedding.
    Catches the same problem described in completely different words.
    Requires a configured Atlas vector search index.
    """
    model        = _get_model()
    vector_index = os.getenv("VECTOR_INDEX_NAME", "vector_index")
    emb_field    = os.getenv("EMBEDDING_FIELD",   "descriptionEmbedding")
    query_vector = model.encode(description.strip(), normalize_embeddings=True).tolist()

    pipeline = [
        {
            "$vectorSearch": {
                "index":         vector_index,
                "path":          emb_field,
                "queryVector":   query_vector,
                "numCandidates": limit * 5,
                "limit":         limit * 2,
            }
        },
        {"$addFields": {"similarity": {"$meta": "vectorSearchScore"}}},
        {
            "$match": {
                "$and": [
                    {"_id":        {"$ne": current_id}},
                    {"similarity": {"$gte": threshold}},
                    _time_window_filter(),
                ]
            }
        },
        {"$limit": limit},
    ]

    results = list(collection.aggregate(pipeline))
    logger.info(f"[PatternTool] Vector search: {len(results)} results (threshold={threshold})")
    return results


# ── Merge and deduplicate ─────────────────────────────────────────────────────

def _merge(structured: List[Dict], vector: List[Dict], limit: int) -> List[Dict]:
    """
    Union of both result sets, deduplicated by _id.
    Structured results take priority (inserted first).
    Records found by both layers appear only once.
    """
    seen:   Dict[str, Dict] = {}

    for doc in structured:
        key = str(doc.get("_id", ""))
        if key not in seen:
            seen[key] = doc

    for doc in vector:
        key = str(doc.get("_id", ""))
        if key not in seen:
            seen[key] = doc

    merged = list(seen.values())[:limit]
    logger.info(
        f"[PatternTool] Merged: {len(structured)} structured + "
        f"{len(vector)} vector = {len(merged)} unique records"
    )
    return merged


# ── Public entry point ────────────────────────────────────────────────────────

def fetch_similar_complaints(
    description: str,
    current_id: str,
    failure_class: Optional[str] = None,
    company_schema: Optional[Dict] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Fetch historical complaints for pattern/trend analysis.

    Runs two layers in parallel and merges the results:
      Layer 1 — type + category + region (structured, deterministic)
      Layer 2 — vector similarity on description (semantic, handles varied wording)

    The LLM receives the merged set and decides which records form a pattern.
    """
    collection = get_capa_complaints_collection()

    # ── Look up current complaint's stored fields ─────────────────
    current_doc = collection.find_one(
        {"_id": current_id},
        {"type": 1, "category": 1, "region": 1},
    )

    current_type     = (current_doc.get("type")     or "").strip() if current_doc else ""
    current_category = (current_doc.get("category") or "").strip() if current_doc else ""
    current_region   = (current_doc.get("region")   or "").strip() if current_doc else ""

    logger.info(
        f"[PatternTool] Complaint '{current_id}' — "
        f"type='{current_type}' category='{current_category}' region='{current_region}'"
    )

    # ── Layer 1: Structured search ────────────────────────────────
    structured_results = _fetch_by_structured_fields(
        collection, current_id,
        current_type, current_category, current_region,
        limit,
    )

    # ── Layer 2: Vector search ────────────────────────────────────
    vector_results = []
    try:
        vector_results = _fetch_by_vector(collection, description, current_id, limit)
    except Exception as e:
        logger.warning(f"[PatternTool] Vector search unavailable: {e}")

    # ── Merge and return ──────────────────────────────────────────
    merged = _merge(structured_results, vector_results, limit)

    if not merged:
        logger.warning(f"[PatternTool] No historical records found for '{current_id}'")
        return []

    return [normalize_document(doc) for doc in merged]
