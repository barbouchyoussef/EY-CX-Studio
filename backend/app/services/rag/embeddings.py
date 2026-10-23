"""Pluggable text embedder for the RAG engine.

Default backend is a **local multilingual** sentence-transformer (``multilingual-e5-small``):
free, offline, no rate limits, and strong on Arabic/French/English -- the mix this product
handles. It rides on the ``torch`` already installed for EasyOCR.

Robustness: if the model or library is unavailable (not yet installed, offline, load error),
the embedder reports ``available = False`` and the vector store transparently falls back to
lexical retrieval. The chatbot therefore never hard-fails on embeddings.

Override with env:
    RAG_EMBED_BACKEND = local | none      (default: local)
    RAG_EMBED_MODEL   = <model name>      (default: intfloat/multilingual-e5-small)
"""

from __future__ import annotations

import logging
import os
import threading

import numpy as np

logger = logging.getLogger(__name__)

_BACKEND = os.getenv("RAG_EMBED_BACKEND", "local").lower()
_MODEL_NAME = os.getenv("RAG_EMBED_MODEL", "intfloat/multilingual-e5-small")
# e5 models are trained with "query:"/"passage:" prefixes; other models want none.
_IS_E5 = "e5" in _MODEL_NAME.lower()


class Embedder:
    """Lazily-loaded local sentence embedder with a hard availability flag."""

    def __init__(self) -> None:
        self._model = None
        self._lock = threading.Lock()
        self._loaded = False
        self._available = False

    @property
    def available(self) -> bool:
        if not self._loaded:
            self._load()
        return self._available

    @property
    def dim(self) -> int | None:
        if self.available and self._model is not None:
            try:
                return int(self._model.get_sentence_embedding_dimension())
            except Exception:
                return None
        return None

    def _load(self) -> None:
        with self._lock:
            if self._loaded:
                return
            self._loaded = True
            if _BACKEND != "local":
                logger.info("RAG embedder disabled (RAG_EMBED_BACKEND=%s); using lexical retrieval.", _BACKEND)
                return
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(_MODEL_NAME)
                self._available = True
                logger.info("RAG embedder loaded: %s (dim=%s)", _MODEL_NAME, self.dim)
            except Exception as exc:
                logger.warning(
                    "RAG local embedder unavailable (%s). Falling back to lexical retrieval. "
                    "Install with: pip install sentence-transformers",
                    exc,
                )

    def _encode(self, texts: list[str], prefix: str) -> np.ndarray:
        prefixed = [f"{prefix}{t}" for t in texts] if prefix else texts
        vecs = self._model.encode(  # type: ignore[union-attr]
            prefixed,
            normalize_embeddings=True,  # unit vectors -> cosine == dot product
            batch_size=16,
            show_progress_bar=False,
        )
        return np.asarray(vecs, dtype=np.float32)

    def embed_passages(self, texts: list[str]) -> np.ndarray | None:
        """Embed documents/chunks for indexing. Returns None if embeddings are unavailable."""
        if not self.available or not texts:
            return None
        with self._lock:
            return self._encode(texts, "passage: " if _IS_E5 else "")

    def embed_query(self, text: str) -> np.ndarray | None:
        """Embed a single query. Returns None if embeddings are unavailable."""
        if not self.available or not text:
            return None
        with self._lock:
            return self._encode([text], "query: " if _IS_E5 else "")[0]


_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
    return _embedder
