"""Chunker guards for the shared RAG engine.

The failure mode this protects against is the native PDF path emitting one page-sized block:
retrieval over whole pages is imprecise and floods the LLM context. The chunker must sub-split
text to a target size, keep tables and captions intact, and carry citation metadata.
"""

from __future__ import annotations

from app.schemas.desk_research import DocumentBlock, ProcessedDocument
from app.services.rag.chunker import _pack_text, chunk_document, chunk_documents


def _doc(blocks, doc_id="d1", filename="report.pdf", status="success"):
    return ProcessedDocument(
        doc_id=doc_id, filename=filename, format="pdf", status=status,
        page_count=3, blocks=blocks, processed_at="2026-07-29T00:00:00Z",
    )


def test_pack_text_respects_target_and_keeps_all_content():
    text = " ".join(f"Sentence number {i} carries value {i}." for i in range(400))
    pieces = _pack_text(text, target=900)
    assert len(pieces) > 1
    assert all(len(p) <= 1000 for p in pieces)  # target + a little slack for the last sentence
    # No sentence's distinctive token is lost.
    joined = " ".join(pieces)
    assert "Sentence number 0 " in joined and "Sentence number 399 " in joined


def test_a_page_sized_block_is_split_into_several_chunks():
    page = ("Contact center handled 2.64M queries in 2024. " * 60).strip()
    chunks = chunk_document(_doc([DocumentBlock(type="paragraph", text=page, page_number=1)]), "ns:1")
    text_chunks = [c for c in chunks if c.kind == "text"]
    assert len(text_chunks) > 1
    assert all(len(c.text) <= 1000 for c in text_chunks)


def test_tables_stay_whole_and_captions_become_their_own_chunk():
    chunks = chunk_document(_doc([
        DocumentBlock(type="heading", level=2, text="Sales", page_number=2),
        DocumentBlock(type="table", table_data=[
            {"Stream": "e-Recharge", "Revenue": "219.4M"},
            {"Stream": "Cards", "Revenue": "110.8M"},
        ], page_number=2),
        DocumentBlock(type="image", image_caption="Bar chart of monthly revenue", page_number=3),
    ]), "ns:1")
    table = [c for c in chunks if c.kind == "table"]
    caption = [c for c in chunks if c.kind == "caption"]
    assert len(table) == 1 and "e-Recharge" in table[0].text and "Cards" in table[0].text
    assert table[0].heading == "Sales"
    assert len(caption) == 1 and "Bar chart" in caption[0].text


def test_metadata_and_heading_context_travel_with_chunks():
    chunks = chunk_document(_doc([
        DocumentBlock(type="heading", level=2, text="Contact Center", page_number=1),
        DocumentBlock(type="paragraph", text="Service level was 55.1% in Q4.", page_number=1),
    ], filename="acme.pdf"), "desk_research:s1")
    assert chunks and all(c.namespace == "desk_research:s1" for c in chunks)
    assert all(c.source_name == "acme.pdf" and c.source_id == "d1" for c in chunks)
    assert chunks[0].heading == "Contact Center"


def test_arabic_text_is_preserved():
    ar = "معدل الخدمة بلغ 55 بالمئة في الربع الرابع من العام."
    chunks = chunk_document(_doc([DocumentBlock(type="paragraph", text=ar, page_number=1)]), "ns:1")
    assert any("معدل" in c.text for c in chunks)


def test_failed_documents_are_skipped():
    good = _doc([DocumentBlock(type="paragraph", text="Real content here about revenue.", page_number=1)], doc_id="g")
    bad = _doc([], doc_id="b", filename="broken.pdf", status="failed")
    chunks = chunk_documents([good, bad], "ns:1")
    assert chunks and all(c.source_id == "g" for c in chunks)
