"""The rescue helpers lifted out of `extract()`.

These paths had no test coverage, and could not easily have had any: they lived five levels deep
inside a 220-line function, reachable only by getting docling to under-extract a real file. Pulling
them into named functions is what makes them testable at all, so the tests come with the move.

What they guard:

  * `_locate_original` — the three-place search for the uploaded file. It was previously written
    out twice, once for PDF and once for PPTX, so the two copies could drift.
  * `_slide_text_lines` — the deepest part of the old function (for slide / for shape / if
    text_frame / for paragraph / if text), and the reason `extract` measured at depth 10.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.services.desk_research.extractor import (
    _locate_original,
    _slide_text_lines,
    has_readable_text,
)


# ── _locate_original ────────────────────────────────────────────────────────────────────────


def test_prefers_the_path_docling_reports(tmp_path: Path):
    real = tmp_path / "converted.pdf"
    real.write_bytes(b"%PDF-")
    result = SimpleNamespace(input=SimpleNamespace(file=str(real)))

    assert _locate_original(result, None, "ignored.pdf") == str(real)


def test_prefers_the_path_the_caller_converted(tmp_path: Path):
    """`source_path` wins, because it is the only candidate guaranteed to exist.

    The pipeline converts a temp copy of the upload, and docling records only that temp file's
    BASENAME -- so `result.input.file` resolves against the CWD and does not exist. Passing the
    real path is what lets the rescue passes open the file at all.
    """
    real = tmp_path / "upload.pdf"
    real.write_bytes(b"%PDF-")
    result = SimpleNamespace(input=SimpleNamespace(file="tmp1234.pdf"))

    assert _locate_original(result, None, "report.pdf", real) == str(real)


def test_falls_back_to_the_stored_original(tmp_path: Path):
    """The upload lives under `<session>/originals/`, and the images dir passed in is
    `<session>/images/<doc_id>` -- so originals is TWO levels up, not one.

    This was off by a level, which silently disabled both rescue passes for every file the
    pipeline processed: a scanned PDF came back as `<!-- image -->` placeholders, marked
    successful, and the model downstream was handed a title with no text under it.
    """
    session = tmp_path / "session"
    originals = session / "originals"
    originals.mkdir(parents=True)
    (originals / "report.pdf").write_bytes(b"%PDF-")
    images_dir = session / "images" / "doc123"      # what _images_dir() actually returns

    result = SimpleNamespace(input=SimpleNamespace(file="/no/such/path.pdf"))
    assert _locate_original(result, images_dir, "report.pdf") == str(originals / "report.pdf")


def test_falls_back_to_the_filename_itself(tmp_path: Path, monkeypatch):
    """A direct call may pass a real path as the filename."""
    here = tmp_path / "direct.pptx"
    here.write_bytes(b"PK")
    monkeypatch.chdir(tmp_path)

    assert _locate_original(SimpleNamespace(), None, "direct.pptx") == "direct.pptx"


def test_returns_none_when_nothing_is_on_disk(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert _locate_original(SimpleNamespace(), None, "missing.pdf") is None


def test_tolerates_a_result_with_no_input_attribute():
    """Guards the getattr chain: not every ConversionResult carries `.input.file`."""
    assert _locate_original(SimpleNamespace(), None, "nope.pdf") is None


# ── _slide_text_lines ───────────────────────────────────────────────────────────────────────


def _para(text: str):
    return SimpleNamespace(text=text)


def _text_shape(*paragraphs: str):
    return SimpleNamespace(
        has_text_frame=True,
        has_table=False,
        text_frame=SimpleNamespace(paragraphs=[_para(p) for p in paragraphs]),
    )


def _table_shape(rows: list[list[str]]):
    return SimpleNamespace(
        has_text_frame=False,
        has_table=True,
        table=SimpleNamespace(
            rows=[SimpleNamespace(cells=[SimpleNamespace(text=c) for c in row]) for row in rows]
        ),
    )


def test_reads_paragraphs_and_drops_blank_ones():
    slide = SimpleNamespace(shapes=[_text_shape("Title", "   ", "Body")])
    assert _slide_text_lines(slide) == ["Title", "Body"]


def test_reads_tables_as_pipe_separated_rows():
    slide = SimpleNamespace(shapes=[_table_shape([["Q1", "10"], ["Q2", "20"]])])
    assert _slide_text_lines(slide) == ["Q1 | 10", "Q2 | 20"]


def test_reads_text_and_tables_in_shape_order():
    slide = SimpleNamespace(shapes=[_text_shape("Heading"), _table_shape([["a", "b"]])])
    assert _slide_text_lines(slide) == ["Heading", "a | b"]


def test_a_slide_with_nothing_readable_yields_nothing():
    """Callers rely on an empty list meaning "skip this slide" rather than an empty block."""
    blank = SimpleNamespace(has_text_frame=False, has_table=False)
    assert _slide_text_lines(SimpleNamespace(shapes=[blank, _text_shape("  ")])) == []


# ── _caption_images_in_markdown ─────────────────────────────────────────────────────────────
# This used to share a try/except with the rescue passes above, so a failure here silently took
# the fallback layers with it. The two are separate stages now; these tests hold the seam open by
# exercising captioning on its own.

from app.schemas.desk_research import DocumentBlock  # noqa: E402
from app.services.desk_research.extractor import _caption_images_in_markdown  # noqa: E402


def _image(caption: str | None, path: str = "img.png") -> DocumentBlock:
    return DocumentBlock(type="image", image_caption=caption, image_path=path)


def test_each_placeholder_takes_the_next_captioned_image_in_order():
    """docling emits placeholders in document order, so position is the whole mapping."""
    markdown = "Intro\n<!-- image -->\nMiddle\n<!-- image -->\nEnd"
    blocks = [_image("A chart of revenue", "a.png"), _image("A team photo", "b.png")]

    out = _caption_images_in_markdown(markdown, blocks)

    assert "<!-- image -->" not in out
    assert out.index("A chart of revenue") < out.index("A team photo")


def test_the_image_path_travels_with_the_caption():
    out = _caption_images_in_markdown("<!-- image -->", [_image("A chart", "figures/x.png")])
    assert "figures/x.png" in out and "A chart" in out


def test_uncaptioned_images_are_not_used():
    """An image the VLM could not describe must not consume a placeholder."""
    out = _caption_images_in_markdown("<!-- image -->", [_image(None), _image("Real caption")])
    assert "Real caption" in out


def test_markdown_with_no_placeholders_is_returned_untouched():
    markdown = "# Report\n\nNothing to caption here."
    assert _caption_images_in_markdown(markdown, [_image("A chart")]) == markdown


def test_no_captioned_images_leaves_the_placeholders_alone():
    """Better a visible placeholder than a caption invented to fill it."""
    markdown = "<!-- image -->"
    assert _caption_images_in_markdown(markdown, [_image(None)]) == markdown


def test_more_placeholders_than_captions_leaves_the_rest_in_place():
    out = _caption_images_in_markdown("<!-- image -->\n<!-- image -->", [_image("Only one")])
    assert "Only one" in out
    assert out.count("<!-- image -->") == 1


# ── has_readable_text ───────────────────────────────────────────────────────────────────────
#
# Docling reports SUCCESS for a file it turned into nothing but picture placeholders. Everything
# downstream then treats it as a document with content: it is counted as "analysed", and the
# deep-dive model is handed a heading with no text under it -- which is how a 4-page dashboard
# PDF produced an invented per-country traffic table in a client report.


def test_only_image_placeholders_is_not_readable():
    """The exact output of the PDF that started this: 4 pages, 46 characters, all placeholders."""
    assert not has_readable_text("<!-- image -->\n\n<!-- image -->\n\n<!-- image -->")


def test_page_headers_around_placeholders_are_not_readable():
    """`extract` adds the `### Page N` markers itself, so they are not evidence of content."""
    assert not has_readable_text("### Page 1\n<!-- image -->\n\n### Page 2\n<!-- image -->")


def test_an_empty_table_skeleton_is_not_readable():
    assert not has_readable_text("| | |\n| --- | --- |\n| | |")


def test_nothing_at_all_is_not_readable():
    for empty in ("", "   \n\n  ", None):
        assert not has_readable_text(empty)


def test_real_prose_is_readable():
    assert has_readable_text("The contact centre answered 55.1% of calls within 20 seconds.")


def test_prose_survives_surrounding_placeholders():
    """A page of charts WITH a caption is a real document; only the empty case is excluded."""
    assert has_readable_text(
        "### Page 1\n<!-- image -->\n\nDirect traffic accounted for most sessions this quarter."
    )


def test_arabic_prose_is_readable():
    """The corpus this guards is largely Arabic -- the check must not be Latin-only."""
    assert has_readable_text("### Page 1\nبلغ إجمالي الاستفسارات والشكاوى المعالجة خلال العام")
