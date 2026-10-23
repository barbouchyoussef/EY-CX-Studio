"""Deciding which search results actually evidence a benchmarked competitor.

The filter that matters is the brand check. Without it the benchmark fills up with vendor
marketing: a CX software page titled "how telecom operators improve retention" reranks beautifully
against a telecom pain point while saying nothing about the operator it is supposed to evidence.

The scoring adjustments are also fixed here from both sides -- they exist to separate candidates
that scored alike, and must never outweigh whether the evidence was relevant at all.
"""

from __future__ import annotations

import pytest

from app.services.assessment.reporting.telecom_semantic_leaders_service import (
    _MAX_DEDUP_PENALTY_STEPS,
    _MAX_DIVERSITY_STEPS,
    _MAX_EVIDENCE_PER_CANDIDATE,
    _SCORE_ADJUSTMENT_STEP,
    _CandidateEvidence,
    _document_names_company,
    SemanticLeadersService,
)


@pytest.fixture
def service():
    return SemanticLeadersService()


def doc(title="", summary="", url="https://example.com/a"):
    return {"title": title, "summary": summary, "url": url}


# ── the brand check ─────────────────────────────────────────────────────────────────────────


def test_the_name_in_the_title_counts(service):
    assert _document_names_company(doc(title="Ooredoo cuts churn"), url="https://x.com/a", company_name="Ooredoo")


def test_the_name_in_the_summary_counts(service):
    assert _document_names_company(doc(summary="A study of Ooredoo."), url="https://x.com/a", company_name="Ooredoo")


def test_the_name_in_the_url_counts(service):
    assert _document_names_company(doc(), url="https://news.com/ooredoo-cx", company_name="Ooredoo")


def test_case_and_spacing_do_not_hide_the_name_in_the_text(service):
    assert _document_names_company(doc(title="ORANGE TUNISIE results"), url="https://x.com/a", company_name="Orange Tunisie")
    assert _document_names_company(doc(title="Orange-Tunisie results"), url="https://x.com/a", company_name="Orange Tunisie")


def test_the_url_check_only_matches_a_name_written_without_separators(service):
    """A known limit: the squashed name is compared against the raw URL, so a hyphenated slug
    misses. Harmless in practice -- such a page nearly always names the company in its title
    too -- but worth fixing here rather than in a caller if it ever matters."""
    assert _document_names_company(doc(), url="https://x.com/orangetunisie-cx", company_name="Orange Tunisie")
    assert not _document_names_company(doc(), url="https://x.com/orange-tunisie-cx", company_name="Orange Tunisie")


def test_a_vendor_page_that_never_names_the_company_is_rejected(service):
    """This is the case the check exists for -- it ranks well and evidences nothing."""
    generic = doc(
        title="How telecom operators improve retention",
        summary="Our platform helps carriers reduce churn.",
        url="https://cx-vendor.com/telecom",
    )
    assert not _document_names_company(generic, url=generic["url"], company_name="Ooredoo")


# ── selecting evidence ──────────────────────────────────────────────────────────────────────


def select(service, documents, ranked):
    return service._select_candidate_evidence(
        reranked=ranked, retrieved_documents=documents, company_name="Ooredoo"
    )


def hit(index, score=0.5):
    return {"index": index, "relevance_score": score}


def test_evidence_is_taken_in_ranked_order(service):
    documents = [doc(title="Ooredoo one", url="https://a.com/1"), doc(title="Ooredoo two", url="https://b.com/2")]
    found = select(service, documents, [hit(1), hit(0)])
    assert [e["url"] for e in found.evidence] == ["https://b.com/2", "https://a.com/1"]


def test_an_out_of_range_index_is_ignored_rather_than_crashing(service):
    """The reranker returns indices into a list it was given; a stale one must not take the run down."""
    documents = [doc(title="Ooredoo one", url="https://a.com/1")]
    found = select(service, documents, [hit(9), hit(-1), hit(0)])
    assert len(found.evidence) == 1


def test_the_same_url_is_never_taken_twice(service):
    documents = [doc(title="Ooredoo billing", url="https://a.com/1"), doc(title="Ooredoo retention", url="https://a.com/1")]
    found = select(service, documents, [hit(0), hit(1)])
    assert len(found.evidence) == 1


def test_pages_that_do_not_name_the_company_are_skipped(service):
    documents = [doc(title="Generic CX advice", url="https://v.com/1"), doc(title="Ooredoo results", url="https://a.com/2")]
    found = select(service, documents, [hit(0), hit(1)])
    assert [e["url"] for e in found.evidence] == ["https://a.com/2"]


def test_collection_stops_at_the_cap(service):
    documents = [doc(title=f"Ooredoo report {i} on retention and billing", url=f"https://s{i}.com/x") for i in range(12)]
    found = select(service, documents, [hit(i) for i in range(12)])
    assert len(found.evidence) == _MAX_EVIDENCE_PER_CANDIDATE


def test_distinct_publishers_are_counted(service):
    documents = [
        doc(title="Ooredoo launches a new billing portal", url="https://a.com/1"),
        doc(title="Ooredoo retention programme wins an award", url="https://b.com/2"),
    ]
    found = select(service, documents, [hit(0), hit(1)])
    assert len(found.unique_domains) == 2


# ── scoring ─────────────────────────────────────────────────────────────────────────────────


def evidence(count=2, domains=1, skips=0, cumulative=1.0):
    return _CandidateEvidence(
        evidence=[{"url": f"u{i}"} for i in range(count)],
        unique_domains={f"d{i}.com" for i in range(domains)},
        dedup_skips=skips,
        cumulative_relevance_score=cumulative,
    )


def test_the_base_score_is_the_average_relevance(service):
    assert evidence(count=4, cumulative=2.0).score().average_relevance == pytest.approx(0.5)


def test_no_evidence_does_not_divide_by_zero(service):
    assert evidence(count=0, cumulative=0.0).score().average_relevance == 0.0


def test_a_single_publisher_earns_no_diversity_bonus(service):
    assert evidence(domains=1).score().diversity_bonus == 0.0


def test_the_diversity_bonus_is_capped(service):
    """Spread is worth something; it is not worth more than relevance."""
    wide = evidence(domains=9).score().diversity_bonus
    assert wide == pytest.approx(_MAX_DIVERSITY_STEPS * _SCORE_ADJUSTMENT_STEP)
    assert wide < 0.05


def test_duplicate_heavy_results_are_penalised_but_only_so_far(service):
    assert evidence(skips=1).score().dedup_penalty == pytest.approx(_SCORE_ADJUSTMENT_STEP)
    assert evidence(skips=50).score().dedup_penalty == pytest.approx(
        _MAX_DEDUP_PENALTY_STEPS * _SCORE_ADJUSTMENT_STEP
    )


def test_adjustments_cannot_outrank_a_genuinely_more_relevant_candidate(service):
    """The whole point of the caps: a 0.9 average beats a 0.5 average whatever the spread."""
    relevant_but_narrow = evidence(count=2, domains=1, cumulative=1.8).score()
    weak_but_broad = evidence(count=2, domains=9, cumulative=1.0).score()
    assert relevant_but_narrow.total > weak_but_broad.total


def test_the_total_combines_the_three_parts(service):
    score = evidence(count=2, domains=3, skips=1, cumulative=1.0).score()
    assert score.total == pytest.approx(
        score.average_relevance + score.diversity_bonus - score.dedup_penalty
    )


# ── assembling the snapshot ─────────────────────────────────────────────────────────────────


def test_internal_bookkeeping_never_reaches_the_report():
    """Every underscore-prefixed key is pipeline state; the report payload must carry none of it."""
    from app.services.assessment.reporting.telecom_semantic_leaders_service import (
        _INTERNAL_LEADER_KEYS,
        _public_leader,
    )

    leader = {
        "key": "ooredoo", "company_name": "Ooredoo", "logo_url": "u", "leader_summary": "s",
        "evidence_links": [{"url": "x"}],
        **{internal: "should not ship" for internal in _INTERNAL_LEADER_KEYS},
    }
    public = _public_leader(leader)
    assert not [k for k in public if k.startswith("_")]
    assert set(public) == {"key", "company_name", "logo_url", "leader_summary", "evidence_links"}


def test_a_leader_with_nothing_internal_is_unchanged():
    from app.services.assessment.reporting.telecom_semantic_leaders_service import _public_leader

    leader = {"key": "k", "company_name": "C"}
    assert _public_leader(leader) == leader


@pytest.mark.parametrize(
    "sector_key, expected",
    [
        ("telecom", "telecommunications"), ("telecom_tn", "telecommunications"),
        ("healthcare", "healthcare"), ("health", "healthcare"),
        ("hospitality", "hospitality"), ("travel", "hospitality"),
    ],
)
def test_sectors_are_searched_under_the_publishers_own_word(sector_key, expected):
    """EY does not file its publications under the assessment's sector names."""
    from app.services.assessment.reporting.telecom_semantic_leaders_service import _sector_label

    assert _sector_label(sector_key, "Ignored") == expected


def test_an_unmapped_sector_falls_back_to_its_own_name():
    from app.services.assessment.reporting.telecom_semantic_leaders_service import _sector_label

    assert _sector_label("banking", "Banking") == "Banking"
    assert _sector_label(None, "Retail") == "Retail"


def test_an_unsupported_snapshot_carries_the_reason_and_no_leaders(service):
    snapshot = service._unsupported_snapshot(
        "LANGSEARCH_API_KEY is not configured.", sector="Telecom", respondent_company_name="Ooredoo"
    )
    assert snapshot["supported"] is False
    assert snapshot["leaders"] == []
    assert "LANGSEARCH_API_KEY" in snapshot["reason"]


def test_coverage_counts_distinct_capabilities_not_links(service):
    """Three links about one capability is weaker evidence than three about three."""
    leaders = [
        {"evidence_links": [{"mapped_capability": "Feedback collection"},
                            {"mapped_capability": "feedback collection"},
                            {"mapped_capability": ""}]},
        {"evidence_links": [{"mapped_capability": "Journey visibility"}]},
        {"evidence_links": []},
    ]
    assert service._capability_coverage_count(leaders) == 2


def test_coverage_of_nothing_is_zero(service):
    assert service._capability_coverage_count([]) == 0
