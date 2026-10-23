"""Unwrapping a vision-model response.

These two parsers came out of `describe_image`, where the same checks were five nested `if`s
inside the request loop. The nesting existed for a real reason: a provider can answer 200 with a
body that contains no text — a safety block, an empty candidate list, a message with a null
content — and each of those had to be checked before reaching the string.

Moving them out turns "another level of indentation" into "return None", and makes the edge cases
directly testable, which they were not before.
"""

from __future__ import annotations

from app.services.desk_research.gemini_vlm import _gemini_text, _openrouter_text


# ── Gemini ──────────────────────────────────────────────────────────────────────────────────


def _gemini(text: str | None) -> dict:
    part = {} if text is None else {"text": text}
    return {"candidates": [{"content": {"parts": [part]}}]}


def test_reads_the_description():
    assert _gemini_text(_gemini("A bar chart of quarterly revenue.")) == "A bar chart of quarterly revenue."


def test_trims_surrounding_whitespace():
    assert _gemini_text(_gemini("  DECORATIVE \n")) == "DECORATIVE"


def test_a_safety_block_returns_none():
    """Gemini answers 200 with no candidates when it refuses; that is not a description."""
    assert _gemini_text({"candidates": [], "promptFeedback": {"blockReason": "SAFETY"}}) is None


def test_a_candidate_with_no_parts_returns_none():
    assert _gemini_text({"candidates": [{"content": {"parts": []}}]}) is None


def test_a_candidate_with_no_content_returns_none():
    assert _gemini_text({"candidates": [{"finishReason": "MAX_TOKENS"}]}) is None


def test_an_empty_string_is_not_a_description():
    """Whitespace-only output must fail over to the next model rather than be stored."""
    assert _gemini_text(_gemini("   ")) is None


def test_a_missing_text_key_returns_none():
    assert _gemini_text(_gemini(None)) is None


def test_an_unrelated_body_returns_none():
    assert _gemini_text({"error": {"code": 400}}) is None


# ── OpenRouter ──────────────────────────────────────────────────────────────────────────────


def test_reads_openrouter_content():
    body = {"choices": [{"message": {"content": "A pie chart."}}]}
    assert _openrouter_text(body) == "A pie chart."


def test_openrouter_empty_choices_returns_none():
    assert _openrouter_text({"choices": []}) is None


def test_openrouter_null_content_returns_none():
    assert _openrouter_text({"choices": [{"message": {"content": None}}]}) is None


def test_openrouter_choices_not_a_list_returns_none():
    """Some gateways answer with an error object where choices should be."""
    assert _openrouter_text({"choices": {"error": "rate limited"}}) is None


def test_openrouter_message_missing_returns_none():
    assert _openrouter_text({"choices": [{"finish_reason": "length"}]}) is None
