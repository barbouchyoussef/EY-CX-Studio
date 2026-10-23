"""Covers the desk-research executive report's map-reduce routing.

The primary use case is "process all kinds of documents and cover every detail". The failure
mode this guards against is the original design: concatenating every document into one prompt,
which silently drops later documents once the combined text outgrows the model window. The
rule verified here is that a large session fans out to per-document extraction and every
document is mapped -- nothing is dropped -- while a small session still takes the cheap
single pass.
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

from app.schemas.desk_research import DocumentBlock, ProcessedDocument
from app.services.desk_research.synthesizer import (
    _MAP_CHUNK_CHARS,
    _chunk_text,
    DeskResearchSynthesizer,
)


def _doc(name: str, n_chars: int) -> ProcessedDocument:
    unit = "Revenue was 12.3M EUR with 4.1% churn in Q3.\n\n"
    md = (unit * (n_chars // len(unit) + 1))[:n_chars]
    return ProcessedDocument(
        doc_id=name,
        filename=f"{name}.pdf",
        format="pdf",
        status="success",
        page_count=3,
        markdown=md,
        blocks=[DocumentBlock(type="paragraph", text="x" * 40, page_number=1)],
        processed_at="2026-07-29T00:00:00Z",
    )


def _run(documents, mapped, filenames_seen):
    """Run the report with a fake gateway that records which prompts it saw."""
    s = DeskResearchSynthesizer()

    async def fake_chat(messages, **_kw):
        system = messages[0]["content"]
        user = messages[1]["content"]
        if "extraction notes" in system:
            mapped.append(user)
            for fn in ("a.pdf", "b.pdf", "c.pdf", "small.pdf"):
                if fn in user:
                    filenames_seen.add(fn)
            return "NOTES: revenue 12.3M EUR, churn 4.1%"
        if "consolidat" in system.lower():
            return "MERGED NOTES: revenue 12.3M EUR, churn 4.1%"
        return "# Executive Desk Research Report: Test\n\nSynthesis body with 12.3M EUR."

    async def go():
        with patch.object(s._gateway, "chat_messages", side_effect=fake_chat):
            return await s.generate_executive_report(documents, "Test Session")

    return asyncio.run(go())


def test_a_single_document_session_still_produces_a_covering_report():
    """A one-document session runs the same pipeline and covers its document.

    This used to assert a "single_pass" strategy that skipped the per-document step for small
    sessions. That shortcut is gone: the synthesizer now always runs the structured pipeline and
    every document gets its own pass, however short. What is left worth guarding is that the
    smallest possible session still completes and still reaches its one document.
    """
    mapped, seen = [], set()
    result = _run([_doc("small", 2_000)], mapped, seen)
    assert result["status"] == "success"
    assert result["strategy"] == "structured"
    assert seen == {"small.pdf"}, "the only document must reach the per-document step"
    assert result["report_markdown"]


def test_every_oversized_document_is_mapped_and_none_is_dropped():
    """The regression this exists for: later documents must never be silently dropped."""
    docs = [_doc("a", 60_000), _doc("b", 60_000), _doc("c", 60_000)]
    assert all(len(d.markdown) > _MAP_CHUNK_CHARS for d in docs), "each must need mapping"
    mapped, seen = [], set()
    result = _run(docs, mapped, seen)
    assert result["status"] == "success"
    assert result["strategy"] == "structured"
    assert seen == {"a.pdf", "b.pdf", "c.pdf"}, "every document must reach the map step"
    assert result["map_calls"] >= 3


def test_the_report_carries_a_figure_through():
    result = _run([_doc("small", 2_000)], [], set())
    assert "12.3M EUR" in result["report_markdown"]


def test_an_empty_session_is_rejected_cleanly():
    empty = ProcessedDocument(
        doc_id="e", filename="e.pdf", format="pdf", status="success",
        markdown="   ", processed_at="2026-07-29T00:00:00Z",
    )
    result = _run([empty], [], set())
    assert result["status"] == "error"


def test_chunker_keeps_chunks_within_budget_and_never_loses_text():
    text = "\n\n".join(f"Paragraph {i} with value {i}0.5%." for i in range(4_000))
    chunks = _chunk_text(text, 48_000)
    assert len(chunks) > 1
    assert all(len(c) <= 48_000 for c in chunks)
    # Every paragraph's distinctive token survives somewhere.
    joined = "\n".join(chunks)
    assert "Paragraph 0 " in joined and "Paragraph 3999 " in joined


def test_native_pdf_extraction_needs_no_docling():
    """A digital (text-layer) PDF must extract without docling -- the memory-heavy page
    rendering is what threw std::bad_alloc on real Arabic reports. This guards the routing."""
    import os

    from app.services.desk_research import converter, extractor

    pdf = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "3rdparty Question and acme answers.pdf")
    pdf = os.path.abspath(pdf)
    if not os.path.exists(pdf):
        import pytest as _pytest
        _pytest.skip("sample PDF not present")

    assert converter.has_text_layer(pdf) is True
    doc = extractor.extract_pdf_native(pdf, "sample.pdf")
    assert doc.status == "success"
    assert doc.page_count and doc.page_count > 0
    assert len(doc.markdown) > 500
    assert any(b.type == "paragraph" and b.page_number for b in doc.blocks)


def test_native_pdf_harvests_and_captions_embedded_images():
    """A digital PDF must keep its figures: embedded images are harvested WITHOUT page
    rendering, deduplicated, and captioned via the VLM (OCR fallback). This guards the gap
    where the native text path used to silently drop every chart/screenshot."""
    import os
    import tempfile
    from unittest.mock import patch

    from app.services.desk_research import extractor

    pdf = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "3rdparty Question and acme answers.pdf")
    pdf = os.path.abspath(pdf)
    if not os.path.exists(pdf):
        import pytest as _pytest
        _pytest.skip("sample PDF not present")

    # Harvest returns embedded images, not page renders (page-sized bitmaps would be huge).
    harvested = extractor.harvest_pdf_images(pdf)
    assert len(harvested) > 0
    assert all("pil_img" in e and e["page_num"] for e in harvested)

    calls = []

    class CountingVLM:
        def describe_image(self, pil):
            calls.append(pil.size)
            return f"caption {pil.size}"

    with tempfile.TemporaryDirectory() as tmp:
        imgdir = extractor.Path(tmp) / "imgs"
        with patch("app.services.desk_research.gemini_vlm.get_vlm_client", return_value=CountingVLM()):
            doc = extractor.extract_pdf_native(pdf, "qa.pdf", imgdir)

        img_blocks = [b for b in doc.blocks if b.type == "image"]
        assert doc.status == "success"
        assert len(img_blocks) == len(harvested), "every harvested image becomes a block"
        assert all(b.image_caption for b in img_blocks), "every figure is captioned"
        # Dedup: a repeated logo is captioned once, so calls < occurrences.
        assert len(calls) < len(img_blocks)
        # Text is still there and the figures are surfaced into the report markdown.
        assert len(doc.markdown) > 500
        assert "### Figures" in doc.markdown


def test_native_pdf_without_images_dir_still_text_only():
    """Backward-compatible: called without images_dir, the native path stays pure text
    (no harvesting, no VLM) -- the fast crash-free path we rely on for plain digital PDFs."""
    import os

    from app.services.desk_research import extractor

    pdf = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "3rdparty Question and acme answers.pdf")
    pdf = os.path.abspath(pdf)
    if not os.path.exists(pdf):
        import pytest as _pytest
        _pytest.skip("sample PDF not present")

    doc = extractor.extract_pdf_native(pdf, "qa.pdf")  # no images_dir
    assert doc.status == "success"
    assert all(b.type != "image" for b in doc.blocks)
    assert "### Figures" not in doc.markdown


def test_chunker_hard_splits_a_single_oversized_paragraph():
    giant = "A" * 120_000  # e.g. one enormous table with no blank lines
    chunks = _chunk_text(giant, 48_000)
    assert all(len(c) <= 48_000 for c in chunks)
    assert sum(len(c) for c in chunks) == 120_000


def _moj(s: str) -> str:
    """Reproduce UTF-8-decoded-as-Latin-1 mojibake exactly as it is stored on disk."""
    return s.encode("utf-8").decode("latin-1")


def test_repair_encoding_fixes_both_scripts_and_preserves_clean_text():
    from app.core.text_normalization import repair_encoding

    # Latin punctuation (English report prose) and Arabic (filenames) both recover.
    assert repair_encoding(_moj("Acme’s 2024–2025")) == "Acme’s 2024–2025"
    assert repair_encoding(_moj("الجودة.pptx")) == "الجودة.pptx"
    # Mixed clean + mojibake in one string: only the broken run is repaired.
    mixed = "café ✓ " + _moj("الجودة")
    assert repair_encoding(mixed) == "café ✓ الجودة"
    # Clean text (legit accents, real Arabic, markdown structure) is untouched.
    for clean in ["Café Größe naïve — déjà", "Real الجودة stays", "# H\n| a | b |\n|-|-|\n| 1 | 2 |"]:
        assert repair_encoding(clean) == clean


def test_report_generation_repairs_mojibake_output():
    """A model that returns mojibake (curly quotes, echoed Arabic filenames) must be healed
    before the report is returned/saved."""
    corrupted = _moj("# Report: Acme’s 2024–2025\n\nSee **الجودة.pptx** for QA criteria.")

    # Drive a run whose model output is mojibake and assert it comes back clean.
    s = DeskResearchSynthesizer()

    async def moj_chat(messages, **_kw):
        return corrupted

    import asyncio as _asyncio
    from unittest.mock import patch

    async def go():
        with patch.object(s._gateway, "chat_messages", side_effect=moj_chat):
            return await s.generate_executive_report([_doc("small", 2_000)], "Test")

    out = _asyncio.run(go())
    assert out["status"] == "success"
    md = out["report_markdown"]
    assert "â" not in md and "Ø" not in md, "mojibake must be repaired"
    assert "Acme’s 2024–2025" in md
    assert "الجودة.pptx" in md


def test_mojibake_recovers_from_either_codec_and_leaves_clean_text_alone():
    """Both ways text gets mangled, across scripts, without touching text that is already fine.

    Latin-1 was the gap. It produces the raw code points U+0080-U+00FF, and the C1 block
    U+0080-U+009F is absent from the CP1252 marker set -- so a run like "â\x80\x99" split after
    the first character and could never be rebuilt. Every curly apostrophe and en dash in an
    English report came through broken.
    """
    from app.core.text_normalization import repair_encoding

    samples = [
        "Acme’s 2024–2025",   # curly apostrophe + en dash: the reported case
        "الجودة",  # Arabic, from an uploaded filename
        "café",                        # a real Latin-1 accent, not mojibake
        "≤ 50%",                       # a 3-byte symbol whose middle byte lands in C1
        "€1,200",
    ]
    for original in samples:
        for codec in ("latin-1", "cp1252"):
            try:
                mangled = original.encode("utf-8").decode(codec)
            except UnicodeDecodeError:
                continue  # not representable that way; nothing to repair
            assert repair_encoding(mangled) == original, f"{codec} mojibake of {original!r}"
        assert repair_encoding(original) == original, f"clean text changed: {original!r}"
