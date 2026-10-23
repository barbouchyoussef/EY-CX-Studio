"""The docling markdown path carries page headers, and falls back rather than losing content.

Docling keeps the page a piece of text came from (``item.prov[0].page_no``) and the extractor
already reads it into ``DocumentBlock.page_number``. The markdown did not carry it:
``export_to_markdown()`` renders the whole document as one string, so a finding drawn from it
could name the document but never the page. The native text-layer path a few hundred lines up
has always emitted ``### Page N``; this makes the two consistent.

The fallbacks matter more than the feature. A report built from a document whose markdown came
back short is worse than one without page headers, so anything unexpected returns the
single-call export.
"""

from __future__ import annotations

import inspect

import pytest

from app.services.desk_research.extractor import _markdown_with_page_headers


class FakeDoclingDoc:
    """Enough of a DoclingDocument for the export logic: `pages` and a per-page markdown export."""

    def __init__(self, per_page: dict[int, str], whole: str):
        self.pages = dict.fromkeys(per_page, 0)
        self._per_page = per_page
        self._whole = whole

    def export_to_markdown(self, page_no: int | None = None, **_kwargs) -> str:
        return self._whole if page_no is None else self._per_page.get(page_no, "")


def test_a_multipage_document_gains_a_header_per_page():
    doc = FakeDoclingDoc(
        {1: "Customer complaints rose", 2: "Handling times doubled", 3: "Recommendations"},
        "Customer complaints rose\n\nHandling times doubled\n\nRecommendations",
    )
    out = _markdown_with_page_headers(doc, 3, "report.pdf")

    assert out.count("### Page ") == 3
    assert "### Page 1\nCustomer complaints rose" in out
    assert "Handling times doubled" in out


def test_a_single_page_document_is_left_alone():
    """One page needs no headers, and adding them would change every existing one-pager."""
    doc = FakeDoclingDoc({1: "Only page"}, "Only page")
    assert _markdown_with_page_headers(doc, 1, "one.pdf") == "Only page"


@pytest.mark.parametrize("page_count", [None, 0])
def test_an_unknown_page_count_uses_the_whole_document_export(page_count):
    doc = FakeDoclingDoc({1: "a", 2: "b"}, "a b")
    assert _markdown_with_page_headers(doc, page_count, "x.pdf") == "a b"


def test_an_empty_page_does_not_shift_the_numbering_of_later_pages():
    """The numbers come from doc.pages, not from counting, so a blank page 2 cannot make page 3
    render as 'Page 2' and send a consultant to the wrong place."""
    doc = FakeDoclingDoc({1: "first", 2: "", 3: "third"}, "first third")
    out = _markdown_with_page_headers(doc, 3, "gap.pdf")

    assert "### Page 1" in out
    assert "### Page 3" in out
    assert "### Page 2" not in out


def test_a_per_page_export_that_loses_content_falls_back():
    """Better a document with no page headers than a shorter document with them."""
    whole = "a much longer whole-document body " * 10
    doc = FakeDoclingDoc({1: "tiny", 2: ""}, whole)

    assert _markdown_with_page_headers(doc, 2, "lossy.pdf") == whole


def test_a_per_page_export_that_raises_falls_back():
    """Older docling builds, or a document type that cannot be paged, must not break extraction."""

    class NoPerPage(FakeDoclingDoc):
        def export_to_markdown(self, page_no: int | None = None, **_kwargs) -> str:
            if page_no is not None:
                raise RuntimeError("per-page export unsupported")
            return self._whole

    doc = NoPerPage({1: "a", 2: "b"}, "whole document text")
    assert _markdown_with_page_headers(doc, 2, "old.pdf") == "whole document text"


def test_the_split_keeps_substantially_all_of_the_text():
    """The guard is a ratio, so a little formatting drift between the two export modes is fine
    while a real loss is not."""
    pages = {1: "x" * 400, 2: "y" * 400, 3: "z" * 400}
    doc = FakeDoclingDoc(pages, "x" * 400 + "y" * 400 + "z" * 400)
    out = _markdown_with_page_headers(doc, 3, "big.pdf")

    for letter in ("x", "y", "z"):
        assert letter * 400 in out


def test_the_extractor_actually_uses_it():
    """The tests above exercise the helper directly, so they would all still pass if the call
    site went back to the plain export. This asserts the wiring."""
    from app.services.desk_research import extractor

    source = inspect.getsource(extractor)
    assert "markdown = _markdown_with_page_headers(doc, page_count, filename)" in source, (
        "the docling path must build its markdown through _markdown_with_page_headers, "
        "not through doc.export_to_markdown() directly"
    )
