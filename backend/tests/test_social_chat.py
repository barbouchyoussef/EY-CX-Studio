"""Social chatbot uses the SHARED agentic engine with a KPI-injection context source.

Proves the reuse story: no RAG, no vector index -- the computed metrics are injected directly,
and the same plan → gather → answer loop produces a grounded, cited answer.
"""

from __future__ import annotations

import asyncio

from app.schemas.scraping import (
    ChannelReportSection,
    DetailedSocialReport,
    FrictionPoint,
    Recommendation,
    ReportEvidence,
    SentimentBreakdown,
    Strength,
    ThemeFrequency,
)
from app.services.scraping import social_chat


def _report() -> DetailedSocialReport:
    return DetailedSocialReport(
        executive_summary="Sentiment is mostly negative, driven by billing and network issues.",
        overall_sentiment=SentimentBreakdown(positive_pct=22.0, neutral_pct=16.0, negative_pct=62.0, classified_count=180),
        evidence=ReportEvidence(
            reviews_collected=210, reviews_with_text=180, reviews_classified=180,
            overall_sentiment=SentimentBreakdown(positive_pct=22.0, neutral_pct=16.0, negative_pct=62.0, classified_count=180),
            top_complaints=[
                ThemeFrequency(label="billing errors", count=48, share_pct=27.0),
                ThemeFrequency(label="network outages", count=33, share_pct=18.0),
            ],
            reply_rate_pct=12.0, reply_rate_base=90,
        ),
        top_friction_points=[FrictionPoint(
            theme="Billing errors", source="scraped",
            description="Customers report being double-charged after plan changes",
            supporting_evidence=["charged twice in March"], mention_count=48, share_pct=27.0,
        )],
        top_strengths=[Strength(text="Fast in-store service", mention_count=15)],
        recommendations=[Recommendation(text="Audit the billing system", addresses="Billing errors", mention_count=48)],
        channel_breakdown=[ChannelReportSection(
            channel="Facebook", summary="High complaint volume about billing on Facebook.",
            friction_points=["billing"], key_stats=["Engagement rate: 3.1%"],
        )],
        methodology_note="Based on scraped reviews only.",
    )


def test_report_to_context_carries_the_full_report():
    ctx = social_chat.report_to_context(_report())
    # KPIs / exact numbers
    assert "62% negative" in ctx
    assert "billing errors (48 mentions, 27%)" in ctx
    assert "REPLY RATE: 12%" in ctx
    assert "Audit the billing system" in ctx
    # Non-KPI narrative that the old serializer dropped is now present:
    assert "double-charged after plan changes" in ctx  # friction description
    assert "charged twice in March" in ctx  # supporting evidence
    assert "[Facebook]" in ctx and "Engagement rate: 3.1%" in ctx  # channel breakdown


def test_social_chat_injects_kpis_and_answers_without_rag():
    captured = {}

    async def fake_llm(system, user):
        captured["system"] = system
        captured["user"] = user
        return "Negative sentiment is **62%**, mostly billing errors."

    out = asyncio.run(social_chat.chat_with_report(_report(), "how bad is sentiment?", llm_fn=fake_llm))
    # The full report was injected (not retrieved) and the report is the cited source.
    assert "Full social report:" in captured["user"]
    assert "62% negative" in captured["user"]
    assert out["sources"] == [social_chat.REPORT_SOURCE]
    assert out["used_context"] is True
    assert "62%" in out["answer"]


def test_social_chat_greeting_skips_injection():
    async def fake_llm(system, user):
        # Planner sees the planner system; answer sees the role prompt.
        if "retrieval planner" in system.lower():
            return '{"needs_search": false, "queries": []}'
        return "Hello! How can I help with the social report?"

    out = asyncio.run(social_chat.chat_with_report(_report(), "hi!", llm_fn=fake_llm))
    assert out["used_context"] is False and out["sources"] == []


def test_small_report_injects_whole_no_index_built(tmp_path, monkeypatch):
    from app.services.rag import store

    monkeypatch.setattr(store, "_RAG_ROOT", tmp_path / "rag")
    src = social_chat.make_report_context_source(_report(), report_id="small-1")
    ctx, sources = asyncio.run(src("sentiment", ["sentiment"]))
    assert ctx.startswith("Full social report:") and sources == [social_chat.REPORT_SOURCE]
    assert not store.has_index("social:small-1"), "small reports inject, no index needed"


def test_report_chat_persistence_roundtrip(tmp_path, monkeypatch):
    from app.services.scraping import report_chat

    monkeypatch.setattr(report_chat, "_CHATS_DIR", str(tmp_path / "chats"))
    fn = "ooredoo_report_20260730_120000.json"

    assert report_chat.load_chat(fn) == []  # nothing yet
    report_chat.append_chat(fn, [
        {"id": "1", "role": "user", "text": "how bad is sentiment?", "ts": 1.0},
        {"id": "2", "role": "assistant", "text": "62% negative.", "sources": ["Social Report"], "ts": 2.0},
    ])
    report_chat.append_chat(fn, [{"id": "3", "role": "user", "text": "and billing?", "ts": 3.0}])

    loaded = report_chat.load_chat(fn)
    assert [m["id"] for m in loaded] == ["1", "2", "3"]  # appends, not overwrites
    assert loaded[1]["sources"] == ["Social Report"]

    report_chat.delete_chat(fn)
    assert report_chat.load_chat(fn) == []


def test_report_chat_heals_mojibake(tmp_path, monkeypatch):
    from app.services.scraping import report_chat

    monkeypatch.setattr(report_chat, "_CHATS_DIR", str(tmp_path / "chats"))
    fn = "brand_report_x.json"
    moj = "Acme’s".encode("utf-8").decode("latin-1")  # stored-mojibake form
    report_chat.append_chat(fn, [{"id": "1", "role": "assistant", "text": moj}])
    assert report_chat.load_chat(fn)[0]["text"] == "Acme’s"


def test_oversized_report_falls_back_to_rag(tmp_path, monkeypatch):
    from app.services.rag import store

    monkeypatch.setattr(store, "_RAG_ROOT", tmp_path / "rag")

    class _Off:  # force lexical retrieval, no model download
        available = False
        def embed_passages(self, texts):
            return None
        def embed_query(self, text):
            return None

    monkeypatch.setattr(store, "get_embedder", lambda: _Off())

    rep = _report()
    rep.executive_summary = "Billing errors frustrate customers repeatedly. " * 1000  # ~47k chars > cap
    src = social_chat.make_report_context_source(rep, report_id="big-1")
    ctx, sources = asyncio.run(src("billing errors", ["billing errors"]))
    assert store.has_index("social:big-1"), "oversized report is indexed for RAG"
    assert ctx and sources == [social_chat.REPORT_SOURCE]
