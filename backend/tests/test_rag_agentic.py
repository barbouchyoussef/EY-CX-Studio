"""Agentic RAG guards: the model decides whether to search, and greetings skip retrieval.

Uses a deterministic fake embedder (no model download) and a fake LLM that returns a planner
JSON on the planner call and an answer on the answer call.
"""

from __future__ import annotations

import asyncio

import numpy as np
import pytest

from app.schemas.rag import RagChunk
from app.services.rag import engine, store

_VOCAB = ["service", "level", "revenue", "recharge", "queries"]


class _FakeEmbedder:
    available = True

    def _vec(self, text):
        low = text.lower()
        v = np.array([float(low.count(w)) for w in _VOCAB], dtype=np.float32)
        n = np.linalg.norm(v)
        return v / n if n else v

    def embed_passages(self, texts):
        return np.vstack([self._vec(t) for t in texts]).astype(np.float32)

    def embed_query(self, text):
        return self._vec(text)


def _chunks(ns):
    return [
        RagChunk(chunk_id="c1", namespace=ns, source_id="d1", source_name="acme.pdf", page=1,
                 text="Service level was 55.1% in Q4 with 2.64M queries."),
        RagChunk(chunk_id="c2", namespace=ns, source_id="d2", source_name="sales.pdf", page=2,
                 text="Revenue from e-recharge reached 219.4M."),
    ]


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "_RAG_ROOT", tmp_path / "rag")
    monkeypatch.setattr(store, "get_embedder", lambda: _FakeEmbedder())


def _make_llm(plan_json: str):
    calls = {"planner": 0, "answer": 0, "last_answer_user": ""}

    async def llm(system, user):
        if "retrieval planner" in system.lower():
            calls["planner"] += 1
            return plan_json
        calls["answer"] += 1
        calls["last_answer_user"] = user
        return "Here is the answer."

    return llm, calls


def test_content_question_triggers_search_and_cites():
    ns = "desk_research:a"
    store.build_index(ns, _chunks(ns))
    llm, calls = _make_llm('{"needs_search": true, "queries": ["service level Q4"]}')

    out = asyncio.run(engine.agentic_answer(
        "What was the Q4 service level?", llm,
        answer_system_prompt="role", context_source=engine.rag_context_source(ns, k=4)))
    assert calls["planner"] == 1 and calls["answer"] == 1
    assert out["used_context"] is True and out["retrieved_count"] > 0
    assert any("acme.pdf" in s for s in out["sources"])
    assert "[Source:" in calls["last_answer_user"]


def test_greeting_skips_search():
    ns = "desk_research:b"
    store.build_index(ns, _chunks(ns))
    llm, calls = _make_llm('{"needs_search": false, "queries": []}')

    out = asyncio.run(engine.agentic_answer(
        "hi there!", llm, answer_system_prompt="role", context_source=engine.rag_context_source(ns)))
    assert out["used_context"] is False
    assert out["sources"] == [] and out["retrieved_count"] == 0
    assert "No supporting context" in calls["last_answer_user"]  # answer still runs, no context
    assert out["answer"] == "Here is the answer."


def test_broken_planner_json_falls_back_to_search():
    ns = "desk_research:c"
    store.build_index(ns, _chunks(ns))
    llm, calls = _make_llm("sorry I cannot decide")  # not JSON

    out = asyncio.run(engine.agentic_answer(
        "revenue from recharge?", llm, answer_system_prompt="role",
        context_source=engine.rag_context_source(ns)))
    assert out["retrieved_count"] > 0  # safe default: it searched anyway
    assert any("sales.pdf" in s for s in out["sources"])


def test_preamble_is_always_available_to_the_answerer():
    ns = "desk_research:d"
    store.build_index(ns, _chunks(ns))
    llm, calls = _make_llm('{"needs_search": false, "queries": []}')

    asyncio.run(engine.agentic_answer(
        "what documents do I have?", llm, answer_system_prompt="role",
        context_source=engine.rag_context_source(ns),
        preamble="Documents in this session: acme.pdf, sales.pdf."))
    assert "acme.pdf, sales.pdf" in calls["last_answer_user"]


def test_a_non_rag_context_source_plugs_into_the_same_loop():
    """The engine is context-source agnostic: a plain injection source (e.g. social KPIs)
    works with zero RAG involved -- proving the shared loop generalizes across modules."""
    async def kpi_source(query, planned_queries):
        return "KPIs: negative sentiment 42%, top complaint: billing.", ["Report KPIs"]

    llm, calls = _make_llm('{"needs_search": true, "queries": ["sentiment"]}')
    out = asyncio.run(engine.agentic_answer(
        "what's the negative sentiment?", llm, answer_system_prompt="role", context_source=kpi_source))
    assert out["used_context"] is True
    assert out["sources"] == ["Report KPIs"]
    assert "negative sentiment 42%" in calls["last_answer_user"]
