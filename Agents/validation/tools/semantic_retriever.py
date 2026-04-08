"""
Semantic Evidence Retriever
In-memory chunk-and-embed approach for large evidence corpora.

Strategy
--------
1. build_evidence_index(records)
   - Splits every evidence record's content into overlapping character chunks.
   - Embeds all chunks in a single batched call using all-MiniLM-L6-v2.
   - Stores chunk texts + embeddings in module-level variables (no disk I/O).

2. retrieve_relevant_chunks(query, top_k)
   - Embeds the query once.
   - Computes cosine similarity against every chunk embedding.
   - Returns the top-k chunks sorted by relevance.

Why in-memory?
--------------
- Same pattern as Agents/cause_generation/tools/semantic_matcher.py
- No external vector DB required
- Embeddings are discarded when the next request rebuilds the index
- The SentenceTransformer model is lazy-loaded and kept alive for reuse
"""

from typing import Any, Dict, List, Optional

import numpy as np

# ---------------------------------------------------------------------------
# Tuneable constants
# ---------------------------------------------------------------------------

CHUNK_SIZE = 1000       # maximum characters per chunk
CHUNK_OVERLAP = 150     # overlap between consecutive chunks
DEFAULT_TOP_K = 6       # number of chunks returned per query
MIN_SIMILARITY = 0.15   # discard chunks below this cosine similarity

# ---------------------------------------------------------------------------
# Module-level in-memory index (rebuilt per request)
# ---------------------------------------------------------------------------

_model = None                          # lazy-loaded SentenceTransformer

_chunk_meta: List[Dict[str, str]] = []   # [{reference_id, source, content}, ...]
_chunk_embeddings: Optional[np.ndarray] = None   # shape (N, embedding_dim)


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

def build_evidence_index(evidence_records: List[Dict[str, Any]]) -> int:
    """
    Chunk and embed all evidence records. Stores results in module-level vars.

    Parameters
    ----------
    evidence_records : list of dicts
        Each dict must have at least "content" (str), and ideally
        "reference_id" (str) and "source" (str).

    Returns
    -------
    int
        Total number of chunks indexed (0 if nothing to index).
    """
    global _chunk_meta, _chunk_embeddings

    # Reset previous index
    _chunk_meta = []
    _chunk_embeddings = None

    all_texts: List[str] = []

    for record in evidence_records:
        content = (record.get("content") or "").strip()
        if not content:
            continue

        ref_id = str(record.get("reference_id") or "unknown")
        source = str(record.get("source") or "unknown")

        for chunk_idx, chunk_text in enumerate(_split_into_chunks(content)):
            _chunk_meta.append({
                "reference_id": ref_id,
                "source": source,
                "content": chunk_text,
            })
            all_texts.append(chunk_text)

    if not all_texts:
        _chunk_embeddings = np.zeros((0, 384), dtype=np.float32)
        return 0

    model = _get_model()
    embeddings = model.encode(all_texts, batch_size=64, show_progress_bar=False, convert_to_numpy=True)

    # Normalise rows so cosine similarity = dot product
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    _chunk_embeddings = (embeddings / norms).astype(np.float32)

    return len(_chunk_meta)


def retrieve_relevant_chunks(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    min_similarity: float = MIN_SIMILARITY,
) -> List[Dict[str, str]]:
    """
    Return the top-k evidence chunks most semantically similar to ``query``.

    Parameters
    ----------
    query : str
        Free-text query (e.g. cause_text + process_step + failure_mode).
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
    global _chunk_meta, _chunk_embeddings

    if not _chunk_meta or _chunk_embeddings is None or len(_chunk_embeddings) == 0:
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
    scores: np.ndarray = _chunk_embeddings.dot(query_vec)

    # Sort descending and take top candidates above threshold
    top_indices = np.argsort(scores)[::-1]

    results: List[Dict[str, str]] = []
    for idx in top_indices:
        if len(results) >= top_k:
            break
        score = float(scores[idx])
        if score < min_similarity:
            break
        chunk = _chunk_meta[int(idx)]
        results.append({
            "reference_id": chunk["reference_id"],
            "source": chunk["source"],
            "content": chunk["content"],
            "similarity_score": round(score, 3),
        })

    return results


def clear_evidence_index() -> None:
    """Discard the current in-memory index (call after a request if desired)."""
    global _chunk_meta, _chunk_embeddings
    _chunk_meta = []
    _chunk_embeddings = None
