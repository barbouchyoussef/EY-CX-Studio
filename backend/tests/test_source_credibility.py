"""What may be cited as evidence in a competitor benchmark.

This filter decides which search results a consultant ends up defending in front of a client, and
it had no tests. It was rewritten from a 172-line function into named collections plus a sequence
of checks; the rewrite was validated by running both versions over 14,784 URL/title/summary
combinations with zero disagreements, and these tests keep that behaviour pinned.

They assert on `source_rejection_reason` rather than the boolean, so a failure says which rule
fired instead of only that something did.
"""

from __future__ import annotations

import pytest

from app.services.assessment.reporting.telecom_semantic_leaders_service import (
    source_rejection_reason,
)


def is_credible(url: str, title: str = "Customer experience transformation", summary=None) -> bool:
    return source_rejection_reason(url, title, summary) is None


# ── what should get through ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("url", [
    "https://www.ey.com/en/insights/customer-experience",
    "https://mckinsey.com/capabilities/growth-marketing-and-sales/our-insights/cx",
    "https://bcg.com/publications/2026/customer-experience-telecom",
    "https://en.ey.com/insights/cx-strategy",
    "https://fr.ey.com/insights/experience-client",
])
def test_analysis_from_a_credible_publisher_is_kept(url):
    assert is_credible(url)


# ── hosts that are never evidence ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("url,fragment", [
    ("https://reddit.com/r/telecom/comments/abc", "unreliable host"),
    ("https://www.trustpilot.com/review/example.com", "unreliable host"),
    ("https://wikipedia.org/wiki/Customer_experience", "unreliable host"),
    ("https://einpresswire.com/article/123", "unreliable host"),
    ("https://apps.apple.com/app/id123", "unreliable host"),
])
def test_complaint_sites_wikis_and_wires_are_rejected(url, fragment):
    """A review aggregator is the subject of a benchmark, not a source for one."""
    reason = source_rejection_reason(url, "Customer experience")
    assert reason and fragment in reason


def test_a_lookalike_domain_is_not_matched_by_accident():
    """`wikipedia.org` is blocked; a different company whose name contains it is not."""
    assert is_credible("https://notwikipedia.com/insights/cx")


# ── not the production site ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("url", [
    "https://staging.example.com/insights/cx",
    "https://dev.example.com/insights/cx",
    "https://admin.example.com/insights/cx",
])
def test_non_production_hosts_are_rejected(url):
    reason = source_rejection_reason(url, "Customer experience")
    assert reason and "non-production subdomain" in reason


# ── language ────────────────────────────────────────────────────────────────────────────────


def test_a_two_letter_subdomain_that_is_not_en_or_fr_is_rejected():
    reason = source_rejection_reason("https://de.example.com/insights", "Customer experience")
    assert reason and "foreign-language subdomain" in reason


def test_en_and_fr_editions_are_allowed():
    assert is_credible("https://en.example.com/insights/cx")
    assert is_credible("https://fr.example.com/insights/cx")


def test_a_language_path_segment_is_rejected():
    reason = source_rejection_reason("https://example.com/de/insights/cx", "Customer experience")
    assert reason and "foreign-language path" in reason


@pytest.mark.parametrize("title,language", [
    ("Die Kundenerfahrung und das Vertrauen sind mit dem Kunden", "German"),
    ("La experiencia del cliente con los servicios para las empresas", "Spanish"),
    ("Guia do produto e atendimento ao cliente", "Portuguese"),
    ("De klantervaring van een bedrijf met die dat in is", "Dutch"),
])
def test_a_foreign_language_title_is_rejected(title, language):
    reason = source_rejection_reason("https://example.com/insights", title)
    assert reason and language in reason


def test_a_single_shared_stopword_does_not_reject_an_english_title():
    """"des" and "in" appear in English too; one hit must not be enough."""
    assert is_credible("https://example.com/insights", "The state of customer experience in telecom")


@pytest.mark.parametrize("title", ["顧客体験の変革", "Опыт клиентов"])
def test_non_latin_titles_are_rejected(title):
    reason = source_rejection_reason("https://example.com/insights", title)
    assert reason and "non-Latin script" in reason


def test_a_non_latin_summary_is_rejected():
    reason = source_rejection_reason("https://example.com/insights", "Customer experience", "顧客体験")
    assert reason and "summary" in reason


# ── page types that are not analysis ────────────────────────────────────────────────────────


@pytest.mark.parametrize("url,fragment", [
    ("https://example.com/press-release/2026/launch", "press-release wire"),
    ("https://example.com/help-center/contact", "help or complaints portal"),
    ("https://example.com/community/discussion/123", "forum or discussion thread"),
    ("https://example.com/privacy-policy", "legal or privacy page"),
    ("https://example.com/checkout/cart", "consumer transaction page"),
    ("https://example.com/hosting/guide", "partner or seller guide"),
])
def test_non_analysis_pages_are_rejected_with_a_named_reason(url, fragment):
    reason = source_rejection_reason(url, "Customer experience")
    assert reason and fragment in reason


@pytest.mark.parametrize("title", [
    "Customer service phone number and helpline",
    "Frequently asked questions",
])
def test_directory_style_titles_are_rejected(title):
    reason = source_rejection_reason("https://example.com/page", title)
    assert reason and "directory or complaints page" in reason


def test_an_unparseable_url_is_rejected_rather_than_raising():
    assert source_rejection_reason("http://[", "Customer experience") is not None
