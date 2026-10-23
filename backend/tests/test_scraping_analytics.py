"""Covers the deterministic half of the social scraping module.

The regression that motivated these tests: classifications were written back onto the
original review list by position, while the prompt had been built from a reordered subset.
Once both Google Maps and Facebook returned 40+ reviews, every label from index 40 onward
landed on a different review than the one it described -- and Trustpilot was never
classified at all.
"""

from __future__ import annotations

import asyncio

import pytest

from app.schemas.scraping import PlatformResult, ReviewClassification, ScrapedReview
from app.services.scraping import classification_service
from app.services.scraping.analytics import (
    compute_rating_sentiment_check,
    compute_reply_rate,
    build_evidence,
    compute_complaint_frequencies,
    compute_platform_sentiment,
    compute_rating_distribution,
    compute_theme_frequencies,
)


def _review(platform: str, text: str, rating: float | None = None) -> ScrapedReview:
    return ScrapedReview(platform=platform, text=text, rating=rating)


def _reviews_sent_to_the_model(messages) -> list[dict]:
    """Pull the review payload back out of the prompt the service built.

    Anchored on the 'Reviews to classify' marker rather than the first JSON-looking span: the
    prompt also contains a response-format example, and a greedy match swallows both.
    """
    import json as _json

    prompt = messages[-1]["content"]
    payload = prompt.split("Reviews to classify:", 1)[1]
    start = payload.index("[")
    end = payload.rindex("]") + 1
    return _json.loads(payload[start:end])


def _classify(review: ScrapedReview, sentiment: str, themes: list[str], complaint: str | None = None):
    review.classification = ReviewClassification(
        sentiment=sentiment, confidence=0.9, themes=themes, complaint_category=complaint
    )
    return review


# --------------------------------------------------------------------------- #
# Sampling                                                                      #
# --------------------------------------------------------------------------- #

def test_sample_keeps_every_review_when_under_the_cap():
    reviews = [_review("Google Maps", f"avis {i}") for i in range(10)]
    assert classification_service._select_balanced_sample(reviews) == reviews


def test_sample_gives_every_platform_a_share_including_trustpilot():
    """Trustpilot used to be excluded from sampling entirely, so its reviews never got
    classified and contributed nothing to the report."""
    reviews = (
        [_review("Google Maps", f"gm {i}") for i in range(200)]
        + [_review("Facebook", f"fb {i}") for i in range(200)]
        + [_review("Trustpilot", f"tp {i}") for i in range(200)]
    )
    sample = classification_service._select_balanced_sample(reviews)

    assert len(sample) == classification_service._MAX_REVIEWS_TO_CLASSIFY
    platforms = {r.platform for r in sample}
    assert platforms == {"Google Maps", "Facebook", "Trustpilot"}

    # Round-robin, so the shares are within one of each other.
    counts = [sum(1 for r in sample if r.platform == p) for p in platforms]
    assert max(counts) - min(counts) <= 1


def test_sample_does_not_starve_a_quiet_channel():
    reviews = (
        [_review("Google Maps", f"gm {i}") for i in range(400)]
        + [_review("Trustpilot", f"tp {i}") for i in range(5)]
    )
    sample = classification_service._select_balanced_sample(reviews)
    assert sum(1 for r in sample if r.platform == "Trustpilot") == 5


# --------------------------------------------------------------------------- #
# The index-mapping regression                                                  #
# --------------------------------------------------------------------------- #

def test_classifications_land_on_the_reviews_they_describe(monkeypatch):
    """Each review's text encodes its identity; the fake gateway labels each one with a
    theme derived from that text. If mapping is correct every review carries its own
    marker back."""

    reviews = (
        [_review("Google Maps", f"gm-{i}") for i in range(60)]
        + [_review("Facebook", f"fb-{i}") for i in range(60)]
        + [_review("Trustpilot", f"tp-{i}") for i in range(60)]
    )

    class FakeGateway:
        async def chat_messages(self, messages):
            import json as _json

            return _json.dumps(
                {
                    "classifications": [
                        {
                            "index": item["index"],
                            "sentiment": "negative",
                            "confidence": 0.9,
                            # Echo the review's own text back as its theme.
                            "themes": [item["text"]],
                            "complaint_category": "Test",
                        }
                        for item in _reviews_sent_to_the_model(messages)
                    ]
                }
            )

    monkeypatch.setattr(classification_service, "get_settings", lambda: object())
    monkeypatch.setattr(classification_service, "build_mistral_gateway", lambda _s: FakeGateway())

    classified, summary = asyncio.run(classification_service.classify_reviews(reviews, "TestBrand"))

    labelled = [r for r in classified if r.classification]
    assert labelled, "expected some reviews to be classified"

    for review in labelled:
        assert review.classification.themes == [review.text], (
            f"review {review.text!r} received the label {review.classification.themes!r}"
        )

    assert summary is not None
    assert summary.negative_pct == 100.0


def test_unsampled_reviews_stay_unclassified_rather_than_inheriting_labels(monkeypatch):
    reviews = [_review("Google Maps", f"gm-{i}") for i in range(400)]

    class FakeGateway:
        async def chat_messages(self, messages):
            import json as _json

            return _json.dumps(
                {
                    "classifications": [
                        {"index": i["index"], "sentiment": "positive", "confidence": 0.9,
                         "themes": ["Accueil"], "complaint_category": None}
                        for i in _reviews_sent_to_the_model(messages)
                    ]
                }
            )

    monkeypatch.setattr(classification_service, "get_settings", lambda: object())
    monkeypatch.setattr(classification_service, "build_mistral_gateway", lambda _s: FakeGateway())

    classified, _ = asyncio.run(classification_service.classify_reviews(reviews, "TestBrand"))
    assert sum(1 for r in classified if r.classification) == classification_service._MAX_REVIEWS_TO_CLASSIFY


def test_a_failing_chunk_does_not_lose_the_other_chunks(monkeypatch):
    reviews = [_review("Google Maps", f"gm-{i}") for i in range(90)]
    calls = {"n": 0}

    class FlakyGateway:
        async def chat_messages(self, messages):
            import json as _json

            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("Mistral 429")
            return _json.dumps(
                {
                    "classifications": [
                        {"index": i["index"], "sentiment": "neutral", "confidence": 0.8,
                         "themes": ["Divers"], "complaint_category": None}
                        for i in _reviews_sent_to_the_model(messages)
                    ]
                }
            )

    monkeypatch.setattr(classification_service, "get_settings", lambda: object())
    monkeypatch.setattr(classification_service, "build_mistral_gateway", lambda _s: FlakyGateway())

    classified, summary = asyncio.run(classification_service.classify_reviews(reviews, "TestBrand"))
    labelled = sum(1 for r in classified if r.classification)
    assert 0 < labelled < 90
    assert summary is not None


def test_malformed_indices_are_ignored(monkeypatch):
    reviews = [_review("Google Maps", f"gm-{i}") for i in range(5)]

    class BadGateway:
        async def chat_messages(self, messages):
            return (
                '{"classifications": ['
                '{"index": 999, "sentiment": "positive", "confidence": 1.0, "themes": [], "complaint_category": null},'
                '{"index": -1, "sentiment": "positive", "confidence": 1.0, "themes": [], "complaint_category": null},'
                '{"index": "x", "sentiment": "positive", "confidence": 1.0, "themes": [], "complaint_category": null},'
                '{"index": 0, "sentiment": "WEIRD", "confidence": 5.0, "themes": ["A","B","C","D"], "complaint_category": null}'
                "]}"
            )

    monkeypatch.setattr(classification_service, "get_settings", lambda: object())
    monkeypatch.setattr(classification_service, "build_mistral_gateway", lambda _s: BadGateway())

    classified, _ = asyncio.run(classification_service.classify_reviews(reviews, "TestBrand"))
    assert sum(1 for r in classified if r.classification) == 1
    only = classified[0].classification
    assert only.sentiment == "neutral"      # unknown sentiment falls back
    assert only.confidence == 1.0           # clamped into range
    assert len(only.themes) == 3            # capped at 3


# --------------------------------------------------------------------------- #
# Label hygiene                                                                 #
# --------------------------------------------------------------------------- #

def test_labels_are_trimmed_deduplicated_and_capped():
    clean = classification_service._clean_labels
    assert clean(["Réseau", "réseau", "  "], limit=3) == ["Réseau"]
    assert len(clean(["A", "B", "C", "D", "E"], limit=3)) == 3
    assert clean([], limit=3) == []


def test_the_prompt_keeps_themes_domain_agnostic():
    """Themes are derived from the reviews, so the module is not telecom-shaped."""
    prompt = classification_service._build_prompt(
        "TestBrand", [_review("Google Maps", "avis")]
    )
    assert "no industry is assumed" in prompt.lower()
    # Examples spanning industries, so themes are not anchored to one sector.
    for hint in ("restaurant", "bank", "telecom"):
        assert hint in prompt.lower()


# --------------------------------------------------------------------------- #
# Theme canonicalisation across chunks                                          #
# --------------------------------------------------------------------------- #

def _with_themes(*theme_lists: list[str]) -> list[ScrapedReview]:
    out = []
    for i, themes in enumerate(theme_lists):
        out.append(_classify(_review("Google Maps", f"avis {i}"), "negative", list(themes)))
    return out


def test_variants_merge_into_the_dominant_spelling():
    """Independent chunks phrase one topic differently; counting raw strings splits it."""
    reviews = _with_themes(
        ["Qualité du réseau"], ["Qualité du réseau"], ["Qualité du réseau"], ["Réseau"]
    )
    classification_service.canonicalize_themes(reviews)
    assert [r.classification.themes for r in reviews] == [["Qualité du réseau"]] * 4


def test_the_dominant_spelling_wins_even_when_it_is_the_shorter_one():
    reviews = _with_themes(["Réseau"], ["Réseau"], ["Réseau"], ["Qualité du réseau"])
    classification_service.canonicalize_themes(reviews)
    assert [r.classification.themes for r in reviews] == [["Réseau"]] * 4


def test_plural_and_accent_variants_merge():
    reviews = _with_themes(["Délais"], ["Délais"], ["Délai"], ["delais"])
    classification_service.canonicalize_themes(reviews)
    assert {t for r in reviews for t in r.classification.themes} == {"Délais"}


def test_distinct_topics_sharing_a_word_are_not_merged():
    """The main over-merge risk: neither token set contains the other, so both survive."""
    reviews = _with_themes(
        ["Qualité du réseau"], ["Qualité du service"], ["Qualité du réseau"], ["Qualité du service"]
    )
    classification_service.canonicalize_themes(reviews)
    assert {t for r in reviews for t in r.classification.themes} == {
        "Qualité du réseau",
        "Qualité du service",
    }


def test_unrelated_themes_are_left_alone():
    reviews = _with_themes(["Facturation"], ["Accueil"], ["Prix"])
    before = [list(r.classification.themes) for r in reviews]
    classification_service.canonicalize_themes(reviews)
    assert [r.classification.themes for r in reviews] == before


def test_a_review_holding_two_variants_ends_up_with_one_theme():
    reviews = _with_themes(["Qualité du réseau"], ["Qualité du réseau"], ["Qualité du réseau", "Réseau"])
    classification_service.canonicalize_themes(reviews)
    assert reviews[2].classification.themes == ["Qualité du réseau"]


def test_canonicalisation_lifts_the_merged_count():
    reviews = _with_themes(["Qualité du réseau"], ["Qualité du réseau"], ["Réseau"])
    platforms = [PlatformResult(platform="Google Maps", status="success",
                                review_count=len(reviews), reviews=reviews)]
    assert len(compute_theme_frequencies(platforms)) == 2   # split before

    classification_service.canonicalize_themes(reviews)
    after = compute_theme_frequencies(platforms)
    assert len(after) == 1
    assert after[0].label == "Qualité du réseau"
    assert after[0].count == 3                              # whole, not 2 + 1


def test_canonicalisation_is_safe_on_empty_and_unclassified_input():
    assert classification_service.canonicalize_themes([]) == {}
    unclassified = [_review("Google Maps", "pas classe")]
    assert classification_service.canonicalize_themes(unclassified) == {}
    assert unclassified[0].classification is None


# --------------------------------------------------------------------------- #
# Complaint dimensions: a fixed, cross-industry analytical frame                #
# --------------------------------------------------------------------------- #

def test_a_complaint_snaps_to_its_dimension_exactly():
    snap = classification_service._snap_complaint
    assert snap("Pricing, billing and fees") == "Pricing, billing and fees"
    assert snap("  product or service quality  ") == "Product or service quality"


def test_a_paraphrased_complaint_lands_on_a_dimension_by_token_overlap():
    """The fragmentation the fixed frame exists to prevent: synonyms must not become rows."""
    snap = classification_service._snap_complaint
    assert snap("Billing problem with fees") == "Pricing, billing and fees"
    assert snap("Endless wait times and delays") == "Wait times and delays"


def test_an_unrecognisable_complaint_becomes_autre_never_free_text():
    snap = classification_service._snap_complaint
    assert snap("xyz incomprehensible zzz") == "Other"
    assert snap(None) is None


def test_every_dimension_is_offered_to_the_model():
    prompt = classification_service._build_prompt(
        "TestBrand", [_review("Google Maps", "avis")]
    )
    for dimension in classification_service._COMPLAINT_DIMENSIONS:
        assert dimension in prompt


def test_model_selected_dimensions_consolidate_perfectly():
    """The production path: the model chooses from the fixed list, so identical dimension
    strings collapse into one counted row -- the failure the live run exposed is closed off.
    Five 'bad service' wordings the model resolves to the quality dimension = one row of 5,
    not five fragments."""
    dimension = "Product or service quality"
    reviews = [
        _classify(_review("Google Maps", f"avis {i}"), "negative", ["Divers"], dimension)
        for i in range(5)
    ]
    platforms = [PlatformResult(platform="Google Maps", status="success",
                                review_count=len(reviews), reviews=reviews)]
    complaints = compute_complaint_frequencies(platforms)
    assert len(complaints) == 1
    assert complaints[0].count == 5


def test_the_fallback_reduces_cardinality_even_on_drift():
    """If the model drifts off the list, snapping still pulls related wordings together and
    sends the rest to 'Autre' -- so the table can never fragment the way it did before, even
    in the worst case. Billing paraphrases with shared vocabulary land on one dimension."""
    snap = classification_service._snap_complaint
    billing = [snap(w) for w in ("Excessive fees", "Opaque billing", "Billing fees")]
    assert set(billing) == {"Pricing, billing and fees"}


# --------------------------------------------------------------------------- #
# Aggregation                                                                   #
# --------------------------------------------------------------------------- #

def _sample_platforms() -> list[PlatformResult]:
    gm = [
        _classify(_review("Google Maps", "facture fausse", 1), "negative", ["Facturation"], "Pricing, billing and fees"),
        _classify(_review("Google Maps", "encore une erreur de facture", 1), "negative", ["Facturation"], "Pricing, billing and fees"),
        _classify(_review("Google Maps", "accueil parfait", 5), "positive", ["Accueil"]),
    ]
    tp = [
        _classify(_review("Trustpilot", "reseau instable", 2), "negative", ["Réseau"], "Reliability and outages"),
        _classify(_review("Trustpilot", "facture incomprehensible", 1), "negative", ["Facturation"], "Pricing, billing and fees"),
        _classify(_review("Trustpilot", "correct", 3), "neutral", ["Réseau"]),
    ]
    return [
        PlatformResult(platform="Google Maps", status="success", review_count=len(gm), reviews=gm),
        PlatformResult(platform="Trustpilot", status="success", review_count=len(tp), reviews=tp,
                       summary_stat="TrustScore 1.6/5", reply_rate_pct=1.7),
        PlatformResult(platform="Facebook", status="error", error_message="boom"),
    ]


def test_theme_frequencies_rank_by_volume_and_expose_negativity():
    themes = compute_theme_frequencies(_sample_platforms())
    assert themes[0].label == "Facturation"
    assert themes[0].count == 3
    assert themes[0].share_pct == 50.0        # 3 of 6 classified reviews
    assert themes[0].negative_pct == 100.0

    reseau = next(t for t in themes if t.label == "Réseau")
    assert reseau.count == 2
    assert reseau.negative_pct == 50.0        # one negative, one neutral


def test_complaint_frequencies_are_a_share_of_negative_reviews():
    complaints = compute_complaint_frequencies(_sample_platforms())
    top = complaints[0]
    assert top.label == "Pricing, billing and fees"
    assert top.count == 3
    assert top.share_pct == 75.0              # 3 of 4 negative reviews


def test_platform_sentiment_puts_the_worst_channel_first():
    per_platform = compute_platform_sentiment(_sample_platforms())
    assert [p.platform for p in per_platform] == ["Google Maps", "Trustpilot"]
    assert per_platform[0].negative_pct == pytest.approx(66.7, abs=0.1)
    trustpilot = per_platform[1]
    assert trustpilot.summary_stat == "TrustScore 1.6/5"
    assert trustpilot.reply_rate_pct == 1.7
    assert trustpilot.avg_rating == 2.0


def test_errored_platforms_are_excluded_from_stats():
    assert all(p.platform != "Facebook" for p in compute_platform_sentiment(_sample_platforms()))


def test_rating_distribution_counts_every_rated_review():
    dist = compute_rating_distribution(_sample_platforms())
    assert dist.total == 6
    assert (dist.one, dist.two, dist.three, dist.four, dist.five) == (3, 1, 1, 0, 1)
    assert dist.average == pytest.approx(2.17, abs=0.01)


def test_evidence_bundles_everything_and_attaches_verbatims():
    evidence = build_evidence(_sample_platforms())
    assert evidence.reviews_collected == 6
    assert evidence.reviews_classified == 6
    assert evidence.overall_sentiment.negative_pct == pytest.approx(66.7, abs=0.1)
    assert evidence.top_themes and evidence.top_complaints
    assert evidence.verbatims

    labels = {t.label for t in evidence.top_themes} | {c.label for c in evidence.top_complaints}
    for verbatim in evidence.verbatims:
        assert verbatim.label in labels
        assert verbatim.platform in {"Google Maps", "Trustpilot"}
        assert verbatim.text


def test_aggregation_is_safe_on_empty_input():
    empty = [PlatformResult(platform="Google Maps", status="empty")]
    assert compute_theme_frequencies(empty) == []
    assert compute_complaint_frequencies(empty) == []
    assert compute_platform_sentiment(empty) == []
    assert compute_rating_distribution(empty) is None

    evidence = build_evidence(empty)
    assert evidence.reviews_classified == 0
    assert evidence.overall_sentiment is None


def test_star_only_reviews_count_toward_ratings_but_not_themes():
    """A star with no comment is still a verdict. Dropping these threw away most of the
    rating data and left the star distribution resting on a fraction of what was collected."""
    reviews = [
        _classify(_review("Google Maps", "service catastrophique", 1), "negative", ["Service client"]),
        _review("Google Maps", "", 1),   # star-only
        _review("Google Maps", "", 5),   # star-only
        _review("Google Maps", "", 4),   # star-only
    ]
    platforms = [PlatformResult(platform="Google Maps", status="success",
                                review_count=len(reviews), reviews=reviews)]
    evidence = build_evidence(platforms)

    assert evidence.reviews_collected == 4
    assert evidence.reviews_with_text == 1
    assert evidence.reviews_classified == 1
    # All four stars are counted, not just the commented one.
    assert evidence.rating_distribution.total == 4
    assert evidence.rating_distribution.average == 2.75
    # Themes and sentiment still describe only what was actually read.
    assert evidence.overall_sentiment.classified_count == 1
    assert evidence.top_themes[0].count == 1


def test_star_only_reviews_are_not_sent_for_classification(monkeypatch):
    """They have no text, so a slot in the sample would be wasted on an empty string."""
    reviews = [
        _review("Google Maps", "un vrai commentaire", 2),
        _review("Google Maps", "", 5),
        _review("Google Maps", "   ", 4),
    ]
    sent: list[int] = []

    class FakeGateway:
        async def chat_messages(self, messages):
            import json as _json
            items = _reviews_sent_to_the_model(messages)
            sent.append(len(items))
            assert all(i["text"].strip() for i in items), "an empty review reached the model"
            return _json.dumps({"classifications": [
                {"index": i["index"], "sentiment": "negative", "confidence": 0.9,
                 "themes": ["Service"], "complaint_category": "Test"} for i in items
            ]})

    monkeypatch.setattr(classification_service, "get_settings", lambda: object())
    monkeypatch.setattr(classification_service, "build_mistral_gateway", lambda _s: FakeGateway())

    asyncio.run(classification_service.classify_reviews(reviews, "TestBrand"))
    assert sent == [1]
    assert reviews[0].classification is not None
    assert reviews[1].classification is None
    assert reviews[2].classification is None


def test_classification_is_skipped_when_nothing_has_text(monkeypatch):
    reviews = [_review("Google Maps", "", 5), _review("Google Maps", "", 1)]

    class ExplodingGateway:
        async def chat_messages(self, _messages):
            raise AssertionError("the model must not be called with no text to classify")

    monkeypatch.setattr(classification_service, "get_settings", lambda: object())
    monkeypatch.setattr(classification_service, "build_mistral_gateway", lambda _s: ExplodingGateway())

    result, summary = asyncio.run(classification_service.classify_reviews(reviews, "TestBrand"))
    assert summary is None
    assert all(r.classification is None for r in result)


def test_unclassified_reviews_are_excluded_from_percentages():
    reviews = [
        _classify(_review("Google Maps", "bien", 5), "positive", ["Accueil"]),
        _review("Google Maps", "jamais classe", 1),  # sampled out — no classification
    ]
    platforms = [PlatformResult(platform="Google Maps", status="success", review_count=2, reviews=reviews)]
    evidence = build_evidence(platforms)
    assert evidence.reviews_collected == 2
    assert evidence.reviews_classified == 1
    assert evidence.overall_sentiment.positive_pct == 100.0
    # Ratings are factual and independent of classification, so both are counted.
    assert evidence.rating_distribution.total == 2


# --------------------------------------------------------------------------- #
# Where each complaint surfaces                                                 #
# --------------------------------------------------------------------------- #

def test_complaints_record_which_channels_they_came_from():
    """A ranked list is only actionable once you know where to go and fix it."""
    gm = [
        _classify(_review("Google Maps", "attente"), "negative", ["Attente"], "Wait times and delays"),
        _classify(_review("Google Maps", "encore attente"), "negative", ["Attente"], "Wait times and delays"),
    ]
    tp = [
        _classify(_review("Trustpilot", "facture"), "negative", ["Facturation"], "Pricing, billing and fees"),
        _classify(_review("Trustpilot", "attente aussi"), "negative", ["Attente"], "Wait times and delays"),
    ]
    platforms = [
        PlatformResult(platform="Google Maps", status="success", review_count=len(gm), reviews=gm),
        PlatformResult(platform="Trustpilot", status="success", review_count=len(tp), reviews=tp),
    ]
    complaints = {c.label: c for c in compute_complaint_frequencies(platforms)}

    assert complaints["Wait times and delays"].by_platform == {"Google Maps": 2, "Trustpilot": 1}
    assert complaints["Pricing, billing and fees"].by_platform == {"Trustpilot": 1}
    # The split must always reconcile with the headline count.
    for c in complaints.values():
        assert sum(c.by_platform.values()) == c.count


def test_themes_also_record_their_channels():
    reviews = [
        _classify(_review("Google Maps", "a"), "positive", ["Accueil"]),
        _classify(_review("Trustpilot", "b"), "negative", ["Accueil"]),
    ]
    platforms = [
        PlatformResult(platform="Google Maps", status="success", review_count=1, reviews=reviews[:1]),
        PlatformResult(platform="Trustpilot", status="success", review_count=1, reviews=reviews[1:]),
    ]
    theme = compute_theme_frequencies(platforms)[0]
    assert theme.by_platform == {"Google Maps": 1, "Trustpilot": 1}


def test_by_platform_is_empty_when_nothing_is_classified():
    empty = [PlatformResult(platform="Google Maps", status="empty")]
    assert compute_complaint_frequencies(empty) == []


# --------------------------------------------------------------------------- #
#  Reply rate and rating/sentiment cross-check                                #
# --------------------------------------------------------------------------- #

def _classified_review(platform, sentiment, rating):
    r = ScrapedReview(platform=platform, text="comment", rating=rating)
    r.classification = ReviewClassification(sentiment=sentiment, confidence=0.9, themes=["X"])
    return r


def test_reply_rate_is_weighted_by_review_volume():
    """A three-review channel must not swing the headline as hard as a big one."""
    platforms = [
        PlatformResult(platform="Trustpilot", status="success", review_count=100,
                       reviews=[_review("Trustpilot", "t") for _ in range(100)],
                       reply_rate_pct=10.0),
        PlatformResult(platform="Google Maps", status="success", review_count=4,
                       reviews=[_review("Google Maps", "g") for _ in range(4)],
                       reply_rate_pct=90.0),
    ]
    pct, base = compute_reply_rate(platforms)
    assert base == 104
    assert pct == round((10.0 * 100 + 90.0 * 4) / 104, 1)  # ~13.1, not 50


def test_reply_rate_is_none_when_no_channel_reports_it():
    platforms = [PlatformResult(platform="Google Maps", status="success", review_count=5,
                                reviews=[_review("Google Maps", "g") for _ in range(5)])]
    pct, base = compute_reply_rate(platforms)
    assert pct is None
    assert base == 0


def test_a_genuine_zero_reply_rate_is_kept_distinct_from_missing():
    """0% ('answers no one') is a finding; None ('not measured') is not."""
    platforms = [PlatformResult(platform="Trustpilot", status="success", review_count=8,
                                reviews=[_review("Trustpilot", "t") for _ in range(8)],
                                reply_rate_pct=0.0)]
    pct, base = compute_reply_rate(platforms)
    assert pct == 0.0
    assert base == 8


def test_rating_sentiment_flags_high_rated_negative_and_low_rated_positive():
    reviews = (
        [_classified_review("Google Maps", "negative", 5.0)]        # rated high, reads bad
        + [_classified_review("Google Maps", "positive", 1.0)]      # rated low, reads good
        + [_classified_review("Google Maps", "negative", 1.0) for _ in range(8)]  # agree
    )
    platforms = [PlatformResult(platform="Google Maps", status="success",
                                review_count=len(reviews), reviews=reviews)]
    check = compute_rating_sentiment_check(platforms)
    assert check is not None
    assert check.both_count == 10
    assert check.high_rating_negative == 1
    assert check.low_rating_positive == 1
    assert check.mismatch_count == 2
    assert check.mismatch_pct == 20.0


def test_rating_sentiment_is_none_below_the_minimum_base():
    reviews = [_classified_review("Google Maps", "negative", 5.0) for _ in range(9)]
    platforms = [PlatformResult(platform="Google Maps", status="success",
                                review_count=9, reviews=reviews)]
    assert compute_rating_sentiment_check(platforms) is None


def test_rating_sentiment_ignores_reviews_missing_a_rating_or_a_classification():
    rated_unclassified = ScrapedReview(platform="Google Maps", text="", rating=5.0)
    classified_unrated = _classified_review("Google Maps", "negative", None)
    good = [_classified_review("Google Maps", "negative", 1.0) for _ in range(10)]
    platforms = [PlatformResult(platform="Google Maps", status="success", review_count=12,
                                reviews=[rated_unclassified, classified_unrated, *good])]
    check = compute_rating_sentiment_check(platforms)
    assert check is not None
    assert check.both_count == 10, "only reviews with BOTH a rating and a classification count"
