"""Integration guard for the RAG-backed session chatbot.

Verifies chat_with_session takes the shared-engine path when a session_id is present: it builds
the index from the session's documents, retrieves relevant chunks, and answers with citations --
without touching the network (the LLM is faked) or a 470MB embedding model (lexical fallback).
"""

from __future__ import annotations

import asyncio

import pytest

from app.schemas.desk_research import DocumentBlock, ProcessedDocument
from app.services.desk_research.synthesizer import DeskResearchSynthesizer
from app.services.rag import store


def _doc(doc_id, filename, text, page=1):
    return ProcessedDocument(
        doc_id=doc_id, filename=filename, format="pdf", status="success", page_count=1,
        blocks=[DocumentBlock(type="paragraph", text=text, page_number=page)],
        markdown=text, processed_at="2026-07-29T00:00:00Z",
    )


@pytest.fixture(autouse=True)
def _isolate_rag_root(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "_RAG_ROOT", tmp_path / "rag")


def test_chat_uses_rag_engine_and_returns_citations():
    docs = [
        _doc("d1", "acme.pdf", "Contact center handled 2.64M queries with 55.1% service level in Q4."),
        _doc("d2", "sales.pdf", "Sales revenue reached 337.1M LYD driven by e-recharge of 219.4M LYD.", page=2),
    ]
    s = DeskResearchSynthesizer()

    captured = {}

    async def fake_chat_llm(system, user):
        captured["user"] = user
        return "The Q4 service level was 55.1%."

    s._chat_llm = fake_chat_llm  # type: ignore[assignment]

    out = asyncio.run(s.chat_with_session(docs, "What was the service level in Q4?", session_id="s-int-1"))

    # Retrieved chunks were assembled into the prompt, and the right document surfaced.
    assert "[Source:" in captured["user"]
    assert "55.1%" in captured["user"]
    assert out["retrieved_blocks_count"] > 0
    assert any("acme.pdf" in src for src in out["sources"])
    assert out["answer"] == "The Q4 service level was 55.1%."


def test_chat_with_no_documents_short_circuits():
    s = DeskResearchSynthesizer()
    out = asyncio.run(s.chat_with_session([], "anything", session_id="s-int-2"))
    assert out["sources"] == [] and "No documents" in out["answer"]
