"""Covers how computed volumes get attached to the report's friction points.

Every number shown next to a friction point must describe the same population as the
sentence beside it. Two ways that broke in practice, both caught on real runs:
  - a label present in both the complaint and theme tables resolved to two different counts;
  - a consultant-only point borrowed a scraped count ("7 mentions" beside "41 opinions").
"""

from __future__ import annotations

import asyncio

import pytest

from app.schemas.scraping import (
    DetailedSocialReport,
    PlatformResult,
    ReviewClassification,
    ScrapedReview,
    ThemeFrequency,
)
from app.services.scraping import social_report_service


def _review(text: str, sentiment: str, themes: list[str], complaint: str | None = None, rating=None):
    r = ScrapedReview(platform="Google Maps", text=text, rating=rating)
    r.classification = ReviewClassification(
        sentiment=sentiment, confidence=0.9, themes=themes, complaint_category=complaint
    )
    return r


def _platforms() -> list[PlatformResult]:
    reviews = [
        _review("facture fausse", "negative", ["Facturation"], "Pricing, billing and fees", 1),
        _review("encore la facture", "negative", ["Facturation"], "Pricing, billing and fees", 1),
        _review("attente interminable", "negative", ["Temps d'attente"], "Wait times and delays", 1),
        _review("accueil parfait", "positive", ["Accueil"], None, 5),
    ]
    return [PlatformResult(platform="Google Maps", status="success",
                           review_count=len(reviews), reviews=reviews)]


def _generate(monkeypatch, model_report: dict, platforms=None, manual=None) -> DetailedSocialReport:
    """Run the real post-processing over a canned model response."""

    class FakeGateway:
        async def chat_messages(self, _messages):
            import json
            return json.dumps(model_report)

    monkeypatch.setattr(social_report_service, "get_settings", lambda: object())
    monkeypatch.setattr(social_report_service, "build_mistral_gateway", lambda _s: FakeGateway())

    report = asyncio.run(
        social_report_service.generate_detailed_social_report(
            "TestBrand", platforms if platforms is not None else _platforms(), manual
        )
    )
    assert report is not None
    return report


_BASE = {
    "executive_summary": "Résumé.",
    "channel_breakdown": [],
    "top_strengths": [],
    "website_assessment": None,
    "recommendations": [],
    "methodology_note": "Note.",
}


def test_a_scraped_point_carries_its_computed_volume(monkeypatch):
    report = _generate(monkeypatch, {
        **_BASE,
        "top_friction_points": [{
            "theme": "Facturation", "source": "scraped",
            "related_label": "Pricing, billing and fees",
            "description": "Doubles prélèvements.", "supporting_evidence": [],
        }],
    })
    point = report.top_friction_points[0]
    assert point.mention_count == 2
    assert point.share_pct is not None
    assert point.related_label == "Pricing, billing and fees"


def _workbook(themes):
    from app.schemas.manual_analysis import ManualAnalysisWorkbook, ThemeInsight

    return ManualAnalysisWorkbook(
        company_name="TestBrand",
        themes=[ThemeInsight(**t) for t in themes],
    )


def test_a_consultant_only_point_is_not_given_a_scraped_count(monkeypatch):
    """The badge would describe a different population than the sentence beside it."""
    report = _generate(monkeypatch, {
        **_BASE,
        "top_friction_points": [{
            "theme": "Délais de raccordement fibre", "source": "consultant",
            "related_label": "Pricing, billing and fees",
            "description": "41 opinions relevées par le consultant.", "supporting_evidence": [],
        }],
    })
    point = report.top_friction_points[0]
    assert point.related_label is None
    # No workbook was supplied, so there is no consultant count to fall back on either.
    assert point.mention_count is None


def test_a_consultant_point_is_quantified_from_the_workbook(monkeypatch):
    """Badge and sentence must cite the same number, taken from the same place."""
    manual = _workbook([{
        "theme": "Délais de livraison", "type": "Friction point", "source": "Facebook",
        "opinions_count": 47, "share_of_mentions": 0.16,
    }])
    report = _generate(monkeypatch, {
        **_BASE,
        "top_friction_points": [{
            "theme": "Délais de livraison", "source": "consultant", "related_label": None,
            "description": "47 opinions signalent des retards.", "supporting_evidence": [],
        }],
    }, manual=manual)
    point = report.top_friction_points[0]
    assert point.mention_count == 47
    assert point.share_pct == 16.0


def test_a_paraphrased_consultant_theme_still_matches(monkeypatch):
    manual = _workbook([{
        "theme": "Service après-vente", "type": "Friction point",
        "opinions_count": 38, "share_of_mentions": 0.13,
    }])
    report = _generate(monkeypatch, {
        **_BASE,
        "top_friction_points": [{
            "theme": "Service après-vente (SAV)", "source": "consultant", "related_label": None,
            "description": "…", "supporting_evidence": [],
        }],
    }, manual=manual)
    assert report.top_friction_points[0].mention_count == 38


def test_a_big_consultant_finding_outranks_a_trivial_scraped_one(monkeypatch):
    """The Mytek regression: a single stray scraped review outranked a 47-opinion
    consultant finding purely because the latter carried no number."""
    manual = _workbook([{
        "theme": "Délais de livraison", "type": "Friction point",
        "opinions_count": 47, "share_of_mentions": 0.16,
    }])
    report = _generate(monkeypatch, {
        **_BASE,
        "top_friction_points": [
            {"theme": "Qualité du produit", "source": "scraped",
             "related_label": "Wait times and delays",
             "description": "1 avis isolé.", "supporting_evidence": []},
            {"theme": "Délais de livraison", "source": "consultant", "related_label": None,
             "description": "47 opinions.", "supporting_evidence": []},
        ],
    }, manual=manual)
    assert report.top_friction_points[0].theme == "Délais de livraison"
    assert report.top_friction_points[0].mention_count == 47


def test_a_corroborated_point_keeps_its_scraped_count(monkeypatch):
    """'both' means the scraped data genuinely backs it, so the number belongs."""
    report = _generate(monkeypatch, {
        **_BASE,
        "top_friction_points": [{
            "theme": "Facturation", "source": "both",
            "related_label": "Pricing, billing and fees",
            "description": "Confirmé par les deux sources.", "supporting_evidence": [],
        }],
    })
    assert report.top_friction_points[0].mention_count == 2


def test_an_invented_label_stays_unquantified(monkeypatch):
    report = _generate(monkeypatch, {
        **_BASE,
        "top_friction_points": [{
            "theme": "Quelque chose", "source": "scraped",
            "related_label": "Catégorie inventée par le modèle",
            "description": "…", "supporting_evidence": [],
        }],
    })
    point = report.top_friction_points[0]
    assert point.mention_count is None
    assert point.related_label is None, "a fabricated label must not be echoed to the reader"


def test_points_are_ranked_by_volume(monkeypatch):
    report = _generate(monkeypatch, {
        **_BASE,
        "top_friction_points": [
            {"theme": "Attente", "source": "scraped", "related_label": "Wait times and delays",
             "description": "…", "supporting_evidence": []},
            {"theme": "Facturation", "source": "scraped", "related_label": "Pricing, billing and fees",
             "description": "…", "supporting_evidence": []},
        ],
    })
    counts = [p.mention_count for p in report.top_friction_points]
    assert counts == [2, 1], "the bigger problem must come first"


def test_a_label_in_both_tables_resolves_to_one_number(monkeypatch):
    """Complaint counts win over theme counts: the two use different denominators."""
    reviews = [
        _review("panne", "negative", ["Reliability and outages"],
                "Reliability and outages", 1),
        _review("encore une panne", "negative", ["Reliability and outages"],
                "Reliability and outages", 1),
        _review("bien", "positive", ["Accueil"], None, 5),
    ]
    platforms = [PlatformResult(platform="Google Maps", status="success",
                                review_count=len(reviews), reviews=reviews)]
    report = _generate(monkeypatch, {
        **_BASE,
        "top_friction_points": [{
            "theme": "Pannes", "source": "scraped",
            "related_label": "Reliability and outages",
            "description": "…", "supporting_evidence": [],
        }],
    }, platforms=platforms)

    point = report.top_friction_points[0]
    ev = report.evidence
    complaint = next(c for c in ev.top_complaints if c.label == "Reliability and outages")
    assert point.mention_count == complaint.count
    assert point.share_pct == complaint.share_pct


def test_evidence_is_attached_and_sentiment_is_computed(monkeypatch):
    report = _generate(monkeypatch, {**_BASE, "top_friction_points": []})
    assert report.evidence is not None
    assert report.evidence.reviews_classified == 4
    s = report.overall_sentiment
    assert s is not None
    assert abs(s.positive_pct + s.neutral_pct + s.negative_pct - 100) < 0.5


def test_a_saved_report_with_plain_string_lists_still_loads(monkeypatch):
    """Every report already on disk holds `["text", ...]`. Structuring these fields must not
    make historic reports unopenable."""
    report = _generate(monkeypatch, {
        **_BASE,
        "top_friction_points": [],
        "top_strengths": ["Staff are widely praised"],
        "recommendations": ["Fix the billing system"],
    })
    assert report.top_strengths[0].text == "Staff are widely praised"
    assert report.recommendations[0].text == "Fix the billing system"
    assert report.recommendations[0].mention_count is None


def test_a_recommendation_carries_the_volume_of_the_friction_it_resolves(monkeypatch):
    report = _generate(monkeypatch, {
        **_BASE,
        "top_friction_points": [{
            "theme": "Facturation", "source": "scraped",
            "related_label": "Pricing, billing and fees",
            "description": "…", "supporting_evidence": [],
        }],
        "recommendations": [
            {"text": "Audit the billing pipeline", "addresses": "Facturation"},
        ],
    })
    rec = report.recommendations[0]
    assert rec.addresses == "Facturation"
    assert rec.mention_count == 2, "must cite the same count as the point it references"


def test_a_paraphrased_addresses_still_matches(monkeypatch):
    report = _generate(monkeypatch, {
        **_BASE,
        "top_friction_points": [{
            "theme": "Facturation", "source": "scraped",
            "related_label": "Pricing, billing and fees",
            "description": "…", "supporting_evidence": [],
        }],
        "recommendations": [{"text": "…", "addresses": "Facturation client"}],
    })
    assert report.recommendations[0].mention_count == 2


def test_an_invented_addresses_is_dropped_not_shown(monkeypatch):
    report = _generate(monkeypatch, {
        **_BASE,
        "top_friction_points": [],
        "recommendations": [{"text": "…", "addresses": "Un thème inventé"}],
    })
    rec = report.recommendations[0]
    assert rec.addresses is None, "an unbacked reference must not reach the reader"
    assert rec.mention_count is None


def test_recommendations_are_ordered_by_the_volume_they_address(monkeypatch):
    report = _generate(monkeypatch, {
        **_BASE,
        "top_friction_points": [
            {"theme": "Facturation", "source": "scraped",
             "related_label": "Pricing, billing and fees",
             "description": "…", "supporting_evidence": []},
            {"theme": "Attente", "source": "scraped",
             "related_label": "Wait times and delays",
             "description": "…", "supporting_evidence": []},
        ],
        "recommendations": [
            {"text": "Small win", "addresses": "Attente"},          # 1 mention
            {"text": "Unattributed idea", "addresses": None},
            {"text": "Big win", "addresses": "Facturation"},        # 2 mentions
        ],
    })
    assert [r.text for r in report.recommendations] == ["Big win", "Small win", "Unattributed idea"]


def test_a_strength_is_quantified_from_the_same_tables(monkeypatch):
    report = _generate(monkeypatch, {
        **_BASE,
        "top_friction_points": [],
        "top_strengths": [{"text": "Warm welcome in store", "related_label": "Accueil"}],
    })
    strength = report.top_strengths[0]
    assert strength.related_label == "Accueil"
    assert strength.mention_count == 1


def test_an_invented_strength_label_stays_unquantified(monkeypatch):
    report = _generate(monkeypatch, {
        **_BASE,
        "top_friction_points": [],
        "top_strengths": [{"text": "…", "related_label": "Label inventé"}],
    })
    assert report.top_strengths[0].related_label is None
    assert report.top_strengths[0].mention_count is None


def test_a_channel_with_no_data_is_dropped(monkeypatch):
    """The model must not invent a section for a channel that was never scraped."""
    report = _generate(monkeypatch, {
        **_BASE,
        "top_friction_points": [],
        "channel_breakdown": [
            {"channel": "Google Maps", "summary": "Réel.", "strengths": [],
             "friction_points": [], "key_stats": []},
            {"channel": "Facebook", "summary": "Inventé.", "strengths": [],
             "friction_points": [], "key_stats": []},
        ],
    })
    assert [c.channel for c in report.channel_breakdown] == ["Google Maps"]


# ── Label matching, at the unit level ───────────────────────────────────────────────────────
# The tests above drive the whole generator. These pin `_quantify_from_labels` directly, since
# it is the one place that decides whether a finding gets a number at all -- and it is now shared
# by friction points and strengths, so a change here moves both.


class _Finding:
    """Stands in for anything carrying a related_label: a friction point or a strength."""

    def __init__(self, related_label=None):
        self.related_label = related_label
        self.mention_count = None
        self.share_pct = None


_COUNTS = {
    "billing errors": ThemeFrequency(label="Billing errors", count=47, share_pct=31.2),
}


def test_label_matching_ignores_case_and_padding():
    """The model echoes the label back as prose, so it arrives capitalised or padded."""
    finding = _Finding("  bILLing ErRoRs ")
    social_report_service._quantify_from_labels(finding, _COUNTS)
    assert finding.mention_count == 47


def test_the_statistics_label_replaces_the_models_rendering_of_it():
    finding = _Finding("billing errors")
    social_report_service._quantify_from_labels(finding, _COUNTS)
    assert finding.related_label == "Billing errors"


def test_a_finding_with_no_label_is_left_untouched():
    finding = _Finding(None)
    social_report_service._quantify_from_labels(finding, _COUNTS)
    assert (finding.related_label, finding.mention_count) == (None, None)
