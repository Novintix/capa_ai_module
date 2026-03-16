import re
import logging
from typing import List, Dict, Any, Optional
from config.mongodb_config import get_complaints_collection

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Field aliases — covers most company schemas
# ─────────────────────────────────────────────────────────────
DESCRIPTION_FIELD_ALIASES = [
    "description",
    "Description_of_issue",
    "issue_description",
    "complaint_description",
    "problem_description",
    "failure_description",
    "details",
    "summary",
    "notes",
]

DATE_FIELD_ALIASES = [
    "created_at",
    "Date_Received",
    "date_received",
    "date",
    "complaint_date",
    "reported_date",
    "received_date",
    "timestamp",
]

ID_FIELD_ALIASES = [
    "complaint_id",
    "NC_ID",
    "nc_id",
    "record_id",
    "issue_id",
    "ticket_id",
    "case_id",
]

# ─────────────────────────────────────────────────────────────
# Failure Class Synonym Map
# triggers  → detect failure class from incoming description
# search    → expand MongoDB query beyond exact keywords
# ─────────────────────────────────────────────────────────────
FAILURE_CLASS_SYNONYMS = {
    "Software/Firmware Failure": {
        "triggers": [
            "firmware", "software", "reboot", "watchdog", "lockout",
            "calculation", "dosage", "miscalculation", "interruption",
            "overcurrent", "overheating", "alarm", "connectivity",
            "display", "keypad", "sensor", "over-infusion", "underdose",
            "overdose", "therapy shutdown", "infusion stop", "discrepancy"
        ],
        "search": [
            "firmware", "software", "reboot", "watchdog", "lockout",
            "calculation", "dosage", "miscalculation", "interruption",
            "overheating", "alarm", "infusion", "therapy", "shutdown",
            "discrepancy", "malfunction", "failure", "error"
        ]
    },
    "Seal Integrity Failure": {
        "triggers": [
            "seal", "sterility", "packaging", "burst", "rupture",
            "sterilization", "breach", "pouch", "integrity"
        ],
        "search": [
            "seal", "sterility", "packaging", "burst", "rupture",
            "sterilization", "breach", "integrity"
        ]
    },
    "Structural Failure": {
        "triggers": [
            "fracture", "crack", "cracking", "fatigue", "bending",
            "deformation", "strut", "porosity", "micro-fracture", "loosening"
        ],
        "search": [
            "fracture", "crack", "fatigue", "bending", "deformation",
            "strut", "loosening", "structural"
        ]
    },
    "Mechanical Failure": {
        "triggers": [
            "stiffness", "binding", "separation", "torque", "clamp",
            "handle", "hinge", "expansion", "motor", "roller", "mechanism"
        ],
        "search": [
            "stiffness", "binding", "separation", "torque", "clamp",
            "motor", "roller", "mechanism", "mechanical"
        ]
    },
    "Surface Defect": {
        "triggers": [
            "abrasion", "scratch", "pitting", "roughness", "coating",
            "corrosion", "machining mark", "burr", "anodizing", "passivation"
        ],
        "search": [
            "abrasion", "scratch", "pitting", "roughness", "coating",
            "corrosion", "burr", "surface"
        ]
    },
    "Calibration Drift": {
        "triggers": [
            "calibration", "drift", "flow rate", "deviation", "accuracy",
            "threshold", "tolerance", "frequency", "transducer"
        ],
        "search": [
            "calibration", "drift", "flow", "deviation",
            "threshold", "tolerance", "transducer"
        ]
    },
    "Reagent Instability": {
        "triggers": [
            "reagent", "assay", "sensitivity", "false negative", "false positive",
            "lot-to-lot", "stability", "contamination", "signal decay"
        ],
        "search": [
            "reagent", "assay", "sensitivity", "false", "stability",
            "contamination", "diagnostic"
        ]
    },
    "Labeling Defect": {
        "triggers": [
            "label", "barcode", "expiry", "lot number", "marking",
            "traceability", "udi", "print"
        ],
        "search": [
            "label", "barcode", "expiry", "marking", "traceability"
        ]
    },
    "Dimensional Non-conformance": {
        "triggers": [
            "dimensional", "tolerance", "geometry", "variance",
            "mismatch", "alignment", "porosity"
        ],
        "search": [
            "dimensional", "tolerance", "geometry", "variance",
            "mismatch", "alignment"
        ]
    },
}

STOP_WORDS = {
    "during", "after", "before", "under", "with", "from", "that",
    "this", "have", "been", "were", "they", "them", "their", "which",
    "when", "where", "observed", "detected", "identified", "found",
    "reported", "noted", "occurred", "causing", "caused", "while",
    "into", "onto", "upon", "over", "within", "between", "through"
}


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def resolve_field(doc: Dict, aliases: List[str]) -> Any:
    for alias in aliases:
        if alias in doc and doc[alias] not in (None, "", []):
            return doc[alias]
    return None


def detect_failure_class(description: str) -> Optional[str]:
    desc_lower = description.lower()
    for class_name, config in FAILURE_CLASS_SYNONYMS.items():
        if any(trigger in desc_lower for trigger in config["triggers"]):
            return class_name
    return None


def extract_keywords(text: str, min_len: int = 4, max_keywords: int = 12) -> List[str]:
    words = re.findall(r'\w+', text.lower())
    keywords = list(dict.fromkeys([
        w for w in words
        if len(w) >= min_len and w not in STOP_WORDS
    ]))
    return keywords[:max_keywords]


def get_doc_id(doc: Dict) -> Optional[str]:
    """Extract any available unique ID from a document."""
    for field in ID_FIELD_ALIASES:
        if field in doc and doc[field]:
            return str(doc[field])
    return str(doc.get("_id", ""))


def normalize_document(doc: Dict) -> Dict:
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])

    desc_value = resolve_field(doc, DESCRIPTION_FIELD_ALIASES)
    doc["description"] = desc_value if desc_value else "No description available"

    date_value = resolve_field(doc, DATE_FIELD_ALIASES)
    if date_value is not None:
        doc["normalized_date"] = (
            date_value.isoformat() if hasattr(date_value, "isoformat")
            else str(date_value)
        )
    else:
        doc["normalized_date"] = "Unknown Date"

    return doc


def build_search_query(keywords: List[str], current_id: str, desc_fields: List[str]) -> Dict:
    """
    Build MongoDB query:
    - OR across all description fields with keyword regex
    - Exclude current complaint via $nor across all ID fields
    """
    regex_pattern = "|".join([re.escape(kw) for kw in keywords])
    regex_query = {"$regex": regex_pattern, "$options": "i"}

    description_conditions = [
        {field: regex_query} for field in desc_fields
    ]

    exclusion_conditions = [
        {field: current_id} for field in ID_FIELD_ALIASES
    ]

    return {
        "$and": [
            {"$or": description_conditions},
            {"$nor": exclusion_conditions}
        ]
    }


def run_fetch(
    collection,
    keywords: List[str],
    current_id: str,
    desc_fields: List[str],
    date_fields: List[str],
    limit: int
) -> List[Dict]:
    """Execute a single MongoDB fetch and return normalized docs."""
    if not keywords:
        return []

    query = build_search_query(keywords, current_id, desc_fields)
    sort_order = [(field, -1) for field in date_fields]

    logger.debug(f"[MongoTool] Query: {query}")

    cursor = collection.find(query).sort(sort_order).limit(limit)
    results = []
    for doc in cursor:
        results.append(normalize_document(doc))

    logger.debug(f"[MongoTool] Fetched {len(results)} records")
    return results


def merge_deduplicate(primary: List[Dict], secondary: List[Dict]) -> List[Dict]:
    """Merge two result lists, deduplicating by ID. Primary comes first."""
    seen_ids = set()
    merged = []

    for doc in primary + secondary:
        doc_id = get_doc_id(doc)
        if doc_id and doc_id not in seen_ids:
            seen_ids.add(doc_id)
            merged.append(doc)
        elif not doc_id:
            merged.append(doc)

    return merged


# ─────────────────────────────────────────────────────────────
# Main Tool
# ─────────────────────────────────────────────────────────────

def fetch_similar_complaints(
    description: str,
    current_id: str,
    company_schema: Optional[Dict] = None,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Two-pass semantic fetch from MongoDB.

    Pass 1 — Keyword match:
        Extracts keywords from the complaint description.
        Searches across all description field aliases.

    Pass 2 — Synonym expansion:
        Detects which failure class the complaint belongs to.
        Searches using ALL synonyms for that class.
        This is what catches NC-112, NC-129, NC-148, NC-183 etc.
        that use different words but same failure type.

    Args:
        description:    Current complaint description
        current_id:     ID to exclude from results
        company_schema: Optional resolved schema from orchestrator
                        If provided, uses company-specific field names
                        If None, uses generic aliases (fallback)
        limit:          Max records per pass
    """
    try:
        collection = get_complaints_collection()

        # Use company-specific field names if provided, else generic aliases
        desc_fields  = (company_schema or {}).get("description_fields", DESCRIPTION_FIELD_ALIASES)
        date_fields  = (company_schema or {}).get("date_fields", DATE_FIELD_ALIASES)

        # ── Pass 1: Direct keyword match ──────────────────────
        keywords = extract_keywords(description)
        logger.info(f"[MongoTool] Pass 1 keywords: {keywords}")

        primary_results = run_fetch(
            collection, keywords, current_id,
            desc_fields, date_fields, limit
        )
        logger.info(f"[MongoTool] Pass 1 results: {len(primary_results)}")

        # ── Pass 2: Failure class synonym expansion ────────────
        # This is the critical pass that finds semantically related
        # records using different terminology
        failure_class = detect_failure_class(description)
        secondary_results = []

        if failure_class:
            synonym_keywords = FAILURE_CLASS_SYNONYMS[failure_class]["search"]
            logger.info(
                f"[MongoTool] Pass 2 — class: '{failure_class}' "
                f"— synonyms: {synonym_keywords}"
            )
            secondary_results = run_fetch(
                collection, synonym_keywords, current_id,
                desc_fields, date_fields, limit
            )
            logger.info(f"[MongoTool] Pass 2 results: {len(secondary_results)}")
        else:
            logger.info("[MongoTool] Pass 2 skipped — no failure class detected")

        # ── Merge & deduplicate ────────────────────────────────
        all_results = merge_deduplicate(primary_results, secondary_results)
        logger.info(f"[MongoTool] Total after dedup: {len(all_results)}")

        return all_results

    except Exception as e:
        raise Exception(f"MongoDB fetch tool failed: {str(e)}")