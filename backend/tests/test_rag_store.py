"""Vector store + engine guards.

Covers both retrieval paths: semantic cosine (with a deterministic fake embedder so we test the
numpy/persistence logic without downloading a 470MB model) and the lexical fallback that keeps
the chatbot working when embeddings are unavailable.
"""

from __future__ import annotations

import asyncio

import numpy as np
import pytest

from app.schemas.rag import RagChunk
from app.services import storage
from app.services.rag import engine, store

_VOCAB = ["service", "level", "revenue", "recharge", "market", "share", "queries", "معدل"]


class _FakeEmbedder:
    """Deterministic bag-of-words embedder over a tiny vocab -> real, controllable cosine."""

    available = True

    def _vec(self, text: str) -> np.ndarray:
        low = text.lower()
        v = np.array([float(low.count(w.lower())) for w in _VOCAB], dtype=np.float32)
        n = np.linalg.norm(v)
        return v / n if n else v

    def embed_passages(self, texts):
        return np.vstack([self._vec(t) for t in texts]).astype(np.float32)

    def embed_query(self, text):
        return self._vec(text)


def _chunks(ns="desk_research:s1"):
    return [
        RagChunk(chunk_id="c1", namespace=ns, source_id="d1", source_name="acme.pdf", page=1,
                 text="Contact center handled 2.64M queries with 55.1% service level in Q4."),
        RagChunk(chunk_id="c2", namespace=ns, source_id="d2", source_name="sales.pdf", page=2,
                 text="Sales revenue reached 337.1M LYD driven by e-recharge."),
        RagChunk(chunk_id="c3", namespace=ns, source_id="d3", source_name="strategy.pdf", page=1,
                 text="Strategy targets 60% market share by 2026."),
    ]


@pytest.fixture(autouse=True)
def _isolate_rag_root(tmp_path, monkeypatch):
    # Point the store at a temp dir so tests never touch real data.
    # The index writes through app.services.storage, so isolating the backend isolates it.
    # `_RAG_ROOT` is a key prefix now, not a path -- patching it stopped isolating anything.
    monkeypatch.setattr(storage, "_backend", storage.DiskBackend(tmp_path))


def test_semantic_retrieval_ranks_by_cosine(monkeypatch):
    monkeypatch.setattr(store, "get_embedder", lambda: _FakeEmbedder())
    ns = "desk_research:s1"
    store.build_index(ns, _chunks(ns))
    assert storage.exists(store._vectors_key(ns)), "vectors must be persisted"

    res = store.query_index(ns, "service level", k=1)
    assert res[0].chunk.chunk_id == "c1"
    res2 = store.query_index(ns, "market share", k=1)
    assert res2[0].chunk.chunk_id == "c3"


def test_lexical_fallback_when_embedder_unavailable(monkeypatch):
    class _Off:
        available = False
        def embed_passages(self, texts):
            return None
        def embed_query(self, text):
            return None

    monkeypatch.setattr(store, "get_embedder", lambda: _Off())
    ns = "desk_research:s2"
    store.build_index(ns, _chunks(ns))
    assert not storage.exists(store._vectors_key(ns)), "no vectors when embedder is off"

    res = store.query_index(ns, "revenue e-recharge", k=1)
    assert res[0].chunk.chunk_id == "c2"  # lexical overlap still finds it


def test_delete_removes_the_index(monkeypatch):
    monkeypatch.setattr(store, "get_embedder", lambda: _FakeEmbedder())
    ns = "desk_research:s3"
    store.build_index(ns, _chunks(ns))
    assert store.has_index(ns)
    store.delete_index(ns)
    assert not store.has_index(ns)
    assert store.query_index(ns, "anything", k=3) == []


def test_engine_answers_with_sources(monkeypatch):
    monkeypatch.setattr(store, "get_embedder", lambda: _FakeEmbedder())
    ns = "desk_research:s4"
    store.build_index(ns, _chunks(ns))

    async def fake_llm(system, user):
        assert "[Source:" in user  # context was assembled
        return "The Q4 service level was 55.1%."

    out = asyncio.run(engine.answer_query(ns, "service level", fake_llm, system_prompt="sys", k=2))
    assert out["retrieved_count"] > 0
    assert out["sources"] and "acme.pdf, p1" in out["sources"]
    assert "55.1%" in out["answer"]


def test_engine_handles_empty_namespace():
    async def fake_llm(system, user):
        return "unused"

    out = asyncio.run(engine.answer_query("desk_research:missing", "q", fake_llm, system_prompt="sys"))
    assert out["retrieved_count"] == 0 and out["sources"] == []
