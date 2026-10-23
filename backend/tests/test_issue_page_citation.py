"""An issue can cite the page it came from, and a page it cannot trust is dropped.

The document an issue came from was never in doubt: pipeline.py sets `inspection_point` from the
chunk label in Python, so it is deterministic. The page is different -- only the model knows which
page a finding was drawn from, so it is the one part that arrives from a prompt and therefore the
one part that has to be validated.

A wrong page is worse than no page. It looks checkable, so a consultant follows it, finds nothing,
and stops trusting every other citation in the log. Everything here is about refusing a value
rather than guessing at one.
"""

from __future__ import annotations

import pytest

from app.services.issue_log.pipeline import _coerce_page


@pytest.mark.parametrize(
    "raw,expected",
    [
        (3, 3),
        ("4", 4),
        ("p. 7", 7),
        ("Page 12", 12),
        ("(p. 2)", 2),
        # The prompt says cite the first page when a point spans several.
        ("pages 3-5", 3),
        (2000, 2000),
    ],
)
def test_a_readable_page_is_kept(raw, expected):
    assert _coerce_page(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "   ",
        "n/a",
        "unknown",
        "the first section",
        0,          # pages are 1-based
        "p. 0",
        -1,         # must not be read as page 1
        "-1",
        99999,      # a five-digit page is a parse error, not a citation
        2001,
    ],
)
def test_anything_unreadable_becomes_no_citation(raw):
    assert _coerce_page(raw) is None


def test_the_deep_dive_prompt_asks_for_pages_only_when_the_source_has_them():
    """A document whose per-page export fell back has no page markers. Told to always cite a page,
    the model would invent one there."""
    from app.services.desk_research.synthesizer import DEEPDIVE_SYSTEM_PROMPT

    assert "(p. 4)" in DEEPDIVE_SYSTEM_PROMPT, "the prompt must show the citation format"
    assert "### Page N" in DEEPDIVE_SYSTEM_PROMPT, "it must key off the marker the extractor emits"
    assert "no page references at all" in DEEPDIVE_SYSTEM_PROMPT, (
        "the instruction must be conditional on the markers being present"
    )


def test_both_issue_log_prompts_carry_the_page_instruction_and_field():
    """The sweep pass returns issues in the same shape as the first pass, so it needs the same
    instruction -- an issue added there must be able to cite a page too."""
    from app.services.issue_log import prompts

    for build in (prompts.generate_system, prompts.sweep_system):
        system = build("document", "English")
        assert "PAGE\n" in system, f"{build.__name__} is missing the page instruction"
        assert '"page": null' in system, f"{build.__name__} does not advertise the page field"
        assert "Never infer or estimate a page" in system


def test_the_export_has_a_page_column_next_to_the_source():
    from app.services.issue_log.export import ISSUE_COLUMNS

    names = [c[1] for c in ISSUE_COLUMNS]
    assert "page" in names, "the spreadsheet must show the page"
    assert names.index("page") == names.index("inspection_point") + 1, (
        "the page belongs beside the document it refers to"
    )


def test_the_pipeline_validates_the_page_rather_than_trusting_it():
    """The other tests exercise _coerce_page directly and would still pass if the assembly wrote
    item['page'] straight through."""
    import inspect

    from app.services.issue_log import pipeline

    source = inspect.getsource(pipeline)
    assert '"page": _coerce_page(item.get("page")),' in source, (
        "the issue must take its page through _coerce_page, not straight from the model"
    )
