"""
Semantic Evidence Retriever
In-memory chunk-and-embed approach for large evidence corpora.

Strategy
--------
1. build_evidence_index(records, request_id)
   - Splits every evidence record's content into overlapping character chunks.
   - Embeds all chunks in a single batched call using all-MiniLM-L6-v2.
   - Stores chunk texts + embeddings keyed by request_id (e.g. complaint_id)
     so concurrent requests never share or overwrite each other's index.

2. retrieve_relevant_chunks(query, request_id, top_k)
   - Embeds the query once.
   - Computes cosine similarity against the request's own chunk embeddings.
   - Returns the top-k chunks sorted by relevance.

Why per-request keyed indexes?
------------------------------
- The original single global index was a concurrency bug: a second request
  arriving while the first was still running validate_causes_node would reset
  the index mid-flight, causing the first request to validate against the
  wrong evidence.
- Indexes are stored in a bounded OrderedDict (max 20 entries) so memory
  remains controlled even under load.
- The SentenceTransformer model is still lazy-loaded once and shared (read-only
  after load, so sharing is safe).
"""

import threading
from collections import OrderedDict
from typing import Any, Dict, List, Optional

import numpy as np

# ---------------------------------------------------------------------------
# Tuneable constants
# ---------------------------------------------------------------------------

CHUNK_SIZE = 1800       # maximum characters per chunk (larger = better context for structured docs)
CHUNK_OVERLAP = 200     # overlap between consecutive chunks
DEFAULT_TOP_K = 6       # number of chunks returned per query
MIN_SIMILARITY = 0.30   # discard chunks below this cosine similarity (raised from 0.15 to cut noise)

# ---------------------------------------------------------------------------
# Per-request in-memory index store (bounded, thread-safe)
# ---------------------------------------------------------------------------

_model = None                          # lazy-loaded SentenceTransformer

_MAX_CACHED_INDEXES = 20               # keep at most this many request indexes in memory
_indexes: OrderedDict = OrderedDict()  # request_id -> {"meta": [...], "embeddings": np.ndarray}
_indexes_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_model():
    """Lazy-load and cache the SentenceTransformer model."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _split_into_chunks(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split text into overlapping character-window chunks."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start += chunk_size - overlap

    return chunks


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_evidence_index(evidence_records: List[Dict[str, Any]], request_id: str = "default") -> int:
    """
    Chunk and embed all evidence records. Stores results keyed by request_id.

    Parameters
    ----------
    evidence_records : list of dicts
        Each dict must have at least "content" (str), and ideally
        "reference_id" (str) and "source" (str).
    request_id : str
        Unique key for this request (e.g. complaint_id). Ensures concurrent
        requests maintain independent indexes and never corrupt each other.

    Returns
    -------
    int
        Total number of chunks indexed (0 if nothing to index).
    """
    chunk_meta: List[Dict[str, str]] = []
    all_texts: List[str] = []

    for record in evidence_records:
        content = (record.get("content") or "").strip()
        if not content:
            continue

        ref_id = str(record.get("reference_id") or "unknown")
        source = str(record.get("source") or "unknown")

        for chunk_text in _split_into_chunks(content):
            chunk_meta.append({
                "reference_id": ref_id,
                "source": source,
                "content": chunk_text,
            })
            all_texts.append(chunk_text)

    if not all_texts:
        chunk_embeddings = np.zeros((0, 384), dtype=np.float32)
        with _indexes_lock:
            _store_index(request_id, chunk_meta, chunk_embeddings)
        return 0

    model = _get_model()
    embeddings = model.encode(all_texts, batch_size=64, show_progress_bar=False, convert_to_numpy=True)

    # Normalise rows so cosine similarity = dot product
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    chunk_embeddings = (embeddings / norms).astype(np.float32)

    with _indexes_lock:
        _store_index(request_id, chunk_meta, chunk_embeddings)

    return len(chunk_meta)


def _store_index(request_id: str, chunk_meta: List[Dict[str, str]], chunk_embeddings: np.ndarray) -> None:
    """Store index for request_id in the bounded OrderedDict (must hold _indexes_lock)."""
    if request_id in _indexes:
        _indexes.move_to_end(request_id)
    _indexes[request_id] = {"meta": chunk_meta, "embeddings": chunk_embeddings}
    # Evict oldest entries when over capacity
    while len(_indexes) > _MAX_CACHED_INDEXES:
        _indexes.popitem(last=False)


def retrieve_relevant_chunks(
    query: str,
    request_id: str = "default",
    top_k: int = DEFAULT_TOP_K,
    min_similarity: float = MIN_SIMILARITY,
) -> List[Dict[str, str]]:
    """
    Return the top-k evidence chunks most semantically similar to ``query``.

    Parameters
    ----------
    query : str
        Free-text query (e.g. cause_text + process_step + failure_mode).
    request_id : str
        Must match the request_id used in build_evidence_index for this request.
    top_k : int
        Maximum number of chunks to return.
    min_similarity : float
        Minimum cosine similarity threshold (0–1).

    Returns
    -------
    list of dicts
        Each dict has keys: reference_id, source, content, similarity_score.
        Empty list if the index has not been built or query is blank.
    """
    with _indexes_lock:
        index = _indexes.get(request_id)

    if not index:
        return []

    chunk_meta = index["meta"]
    chunk_embeddings = index["embeddings"]

    if not chunk_meta or chunk_embeddings is None or len(chunk_embeddings) == 0:
        return []

    query = query.strip()
    if not query:
        return []

    model = _get_model()
    query_vec = model.encode([query], convert_to_numpy=True)[0]

    # Normalise query vector
    q_norm = np.linalg.norm(query_vec)
    if q_norm > 0:
        query_vec = query_vec / q_norm

    # Cosine similarity (dot product of normalised vectors)
    scores: np.ndarray = chunk_embeddings.dot(query_vec)

    # Sort descending and take top candidates above threshold
    top_indices = np.argsort(scores)[::-1]

    results: List[Dict[str, str]] = []
    for idx in top_indices:
        if len(results) >= top_k:
            break
        score = float(scores[idx])
        if score < min_similarity:
            break
        chunk = chunk_meta[int(idx)]
        results.append({
            "reference_id": chunk["reference_id"],
            "source": chunk["source"],
            "content": chunk["content"],
            "similarity_score": round(score, 3),
        })

    return results
