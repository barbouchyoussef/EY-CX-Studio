"""Per-namespace vector store, persisted through the shared storage adapter.

One index per namespace (e.g. ``desk_research:<session_id>``). Small by nature -- a session is
tens to a few hundred chunks -- so a brute-force cosine over a numpy matrix is instant and needs
no vector database. When embeddings are unavailable, ``query_index`` falls back to lexical
(keyword-overlap) scoring over the same stored chunks, so retrieval degrades instead of breaking.

Storage: the index goes through ``app.services.storage`` rather than straight to local disk, so it
lives wherever the session's documents live (object storage in production). Writing it to the
container's filesystem would lose every index on redeploy, and silently downgrade the chatbot to
lexical retrieval.

Because that backend may be remote, a loaded index is memoised per namespace: a chat turn runs
several retrievals and must not re-download the vectors each time. ``build_index`` and
``delete_index`` drop the entry, so the cache can never serve a stale index within a process.
"""

from __future__ import annotations

import io
import json
import logging
import os
import re
import threading

import numpy as np

from app.schemas.rag import RagChunk, RetrievedChunk
from app.services import storage
from app.services.rag.embeddings import get_embedder

logger = logging.getLogger(__name__)

_RAG_ROOT = os.getenv("RAG_DATA_ROOT", "rag_data")  # storage key prefix, not a filesystem path
_WORD = re.compile(r"\w+", re.UNICODE)  # \w matches Arabic letters too, so lexical works multilingually

# Minimum cosine similarity for a semantic hit to be kept. Default 0.0 = keep top-k regardless:
# e5 scores are compressed (relevant ~0.80-0.88, unrelated ~0.72), so an absolute cutoff is
# brittle -- we favor recall and let the answering prompt decline when context doesn't fit.
# Set RAG_MIN_SCORE (e.g. 0.78) to drop weak matches instead.
_MIN_SCORE = float(os.getenv("RAG_MIN_SCORE", "0.0"))

# namespace -> (chunks, vectors | None). Guarded because retrieval runs in a thread pool.
_cache: dict[str, tuple[list[RagChunk], np.ndarray | None]] = {}
_cache_lock = threading.Lock()


def _safe(namespace: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", namespace)


def _chunks_key(namespace: str) -> str:
    return f"{_RAG_ROOT}/{_safe(namespace)}/chunks.json"


def _vectors_key(namespace: str) -> str:
    return f"{_RAG_ROOT}/{_safe(namespace)}/vectors.npy"


def _invalidate(namespace: str) -> None:
    with _cache_lock:
        _cache.pop(namespace, None)


def build_index(namespace: str, chunks: list[RagChunk]) -> int:
    """(Re)build the index for a namespace: persist chunks and, if possible, their vectors."""
    storage.put_text(
        _chunks_key(namespace),
        json.dumps([c.model_dump() for c in chunks], ensure_ascii=False),
    )

    vecs = get_embedder().embed_passages([c.text for c in chunks]) if chunks else None
    if vecs is not None:
        buf = io.BytesIO()
        np.save(buf, vecs)
        storage.put_bytes(_vectors_key(namespace), buf.getvalue(), "application/octet-stream")
    else:
        # Drop stale vectors so a later query cleanly falls back to lexical instead of
        # scoring the new chunks against the previous index's matrix.
        try:
            storage.delete(_vectors_key(namespace))
        except Exception:
            pass

    _invalidate(namespace)
    logger.info("RAG index built for %s: %d chunks (vectors=%s)", namespace, len(chunks), vecs is not None)
    return len(chunks)


def _load(namespace: str) -> tuple[list[RagChunk], np.ndarray | None]:
    """Chunks and vectors for a namespace, memoised. Missing index -> ([], None)."""
    with _cache_lock:
        hit = _cache.get(namespace)
    if hit is not None:
        return hit

    chunks: list[RagChunk] = []
    try:
        raw = storage.get_text(_chunks_key(namespace))
        chunks = [RagChunk(**c) for c in json.loads(raw)]
    except Exception:
        logger.debug("No RAG chunks stored for %s", namespace)
        return [], None

    vecs: np.ndarray | None = None
    try:
        vecs = np.load(io.BytesIO(storage.get_bytes(_vectors_key(namespace))))
        if vecs.shape[0] != len(chunks):
            # Chunks and vectors are written together; a mismatch means one write failed.
            logger.warning("RAG vectors for %s do not match chunk count; using lexical.", namespace)
            vecs = None
    except Exception:
        vecs = None

    with _cache_lock:
        _cache[namespace] = (chunks, vecs)
    return chunks, vecs


def has_index(namespace: str) -> bool:
    with _cache_lock:
        if namespace in _cache:
            return bool(_cache[namespace][0])
    return storage.exists(_chunks_key(namespace))


def _lexical(chunks: list[RagChunk], query: str, k: int) -> list[RetrievedChunk]:
    q_words = {w.lower() for w in _WORD.findall(query) if len(w) > 2}
    scored: list[tuple[int, RagChunk]] = []
    for c in chunks:
        c_words = {w.lower() for w in _WORD.findall(c.text)}
        s = len(q_words & c_words)
        if s > 0:
            scored.append((s, c))
    scored.sort(key=lambda t: t[0], reverse=True)
    if not scored:
        # Nothing matched: return the opening chunks so the LLM still has grounding.
        return [RetrievedChunk(chunk=c, score=0.0) for c in chunks[:k]]
    return [RetrievedChunk(chunk=c, score=float(s)) for s, c in scored[:k]]


def query_index(namespace: str, query: str, k: int = 6) -> list[RetrievedChunk]:
    """Return the top-k chunks for a query: semantic cosine when vectors exist, else lexical."""
    chunks, vecs = _load(namespace)
    if not chunks:
        return []

    embedder = get_embedder()
    if vecs is not None and embedder.available:
        try:
            qv = embedder.embed_query(query)
            if qv is not None:
                sims = vecs @ qv  # both normalized -> cosine similarity
                top = np.argsort(-sims)[:k]
                return [
                    RetrievedChunk(chunk=chunks[int(i)], score=float(sims[int(i)]))
                    for i in top
                    if float(sims[int(i)]) >= _MIN_SCORE
                ]
        except Exception:
            logger.warning("Semantic query failed for %s; using lexical.", namespace, exc_info=True)

    return _lexical(chunks, query, k)


def delete_index(namespace: str) -> None:
    _invalidate(namespace)
    try:
        storage.delete_prefix(f"{_RAG_ROOT}/{_safe(namespace)}")
    except Exception:
        logger.warning("Could not delete RAG index for %s", namespace, exc_info=True)
