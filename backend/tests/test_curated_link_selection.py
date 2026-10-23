"""Choosing which evidence links appear under a sector leader.

The rule is a greedy pick with a bonus for capabilities not yet represented, and it exists to stop
a specific failure: the top three links by score are frequently three articles about the same
capability, which reads as one point made three times rather than as evidence across the leader's
practice.

The bonus is a tie-breaker, not a reordering -- these tests fix it from both sides, because
replacing this with a plain "top three by score" is the obvious simplification and it is wrong.
"""

from __future__ import annotations

import pytest

from app.services.assessment.reporting.telecom_semantic_leaders_service import (
    _MAX_CURATED_LINKS,
    _NEW_CAPABILITY_BONUS,
    SemanticLeadersService,
)


@pytest.fixture
def service():
    return SemanticLeadersService()


def candidate(name: str, score: float, capability: str = "feedback", rejected: str | None = None):
    return {
        "url": f"https://example.com/{name}",
        "title": name,
        "selection_score": score,
        "matched_capability": capability,
        "rejection_reason": rejected,
    }


def names(picked):
    return [c["title"] for c in picked]


# ── what is eligible ────────────────────────────────────────────────────────────────────────


def test_rejected_candidates_never_enter_the_running(service):
    picked = service._pick_diverse_links([
        candidate("kept", 0.9),
        candidate("dropped", 1.0, rejected="marketing page"),
    ])
    assert names(picked) == ["kept"]


def test_fewer_candidates_than_slots_returns_them_all(service):
    given = [candidate("a", 0.9, "x"), candidate("b", 0.8, "y")]
    assert len(service._pick_diverse_links(given)) == 2


def test_never_more_than_the_cap(service):
    given = [candidate(str(i), float(i), f"cap{i}") for i in range(9)]
    assert len(service._pick_diverse_links(given)) == _MAX_CURATED_LINKS


def test_no_candidates_is_an_empty_list(service):
    assert service._pick_diverse_links([]) == []


# ── the ranking ─────────────────────────────────────────────────────────────────────────────


def test_the_strongest_link_is_always_taken_first(service):
    picked = service._pick_diverse_links([
        candidate("weak", 0.1, "a"),
        candidate("strong", 0.9, "b"),
        candidate("middling", 0.5, "c"),
    ])
    assert names(picked)[0] == "strong"


def test_a_missing_score_is_treated_as_zero_rather_than_crashing(service):
    picked = service._pick_diverse_links([
        {"url": "u", "title": "unscored", "matched_capability": "a", "rejection_reason": None},
        candidate("scored", 0.4, "b"),
    ])
    assert names(picked)[0] == "scored"


# ── the diversity bonus, from both sides ────────────────────────────────────────────────────


def test_a_new_capability_wins_a_near_tie(service):
    """0.48 + the bonus clears 0.50, so the second slot goes to the unrepresented capability."""
    assert _NEW_CAPABILITY_BONUS == pytest.approx(0.05)
    picked = service._pick_diverse_links([
        candidate("first", 0.90, "feedback"),
        candidate("same-capability", 0.50, "feedback"),
        candidate("new-capability", 0.48, "journeys"),
    ])
    assert names(picked) == ["first", "new-capability", "same-capability"]


def test_the_bonus_cannot_promote_a_genuinely_weaker_link(service):
    """0.40 + the bonus still loses to 0.50: breadth breaks ties, it does not override quality."""
    picked = service._pick_diverse_links([
        candidate("first", 0.90, "feedback"),
        candidate("same-capability", 0.50, "feedback"),
        candidate("new-capability", 0.40, "journeys"),
    ])
    assert names(picked)[1] == "same-capability"


def test_three_links_on_one_capability_are_still_returned_when_that_is_all_there_is(service):
    """Breadth is preferred, never required -- a leader with one strong theme still gets links."""
    picked = service._pick_diverse_links([
        candidate("a", 0.9, "feedback"),
        candidate("b", 0.8, "feedback"),
        candidate("c", 0.7, "feedback"),
        candidate("d", 0.6, "feedback"),
    ])
    assert names(picked) == ["a", "b", "c"]


def test_each_capability_only_earns_the_bonus_until_it_is_covered(service):
    """Once journeys is represented, its remaining candidates compete on score alone."""
    picked = service._pick_diverse_links([
        candidate("feedback-top", 0.90, "feedback"),
        candidate("journeys-top", 0.60, "journeys"),
        candidate("journeys-second", 0.58, "journeys"),
        candidate("feedback-second", 0.59, "feedback"),
    ])
    assert names(picked) == ["feedback-top", "journeys-top", "feedback-second"]


def test_the_same_link_is_never_picked_twice(service):
    picked = service._pick_diverse_links([candidate("a", 0.9, "x"), candidate("b", 0.9, "x")])
    assert len(picked) == len({id(c) for c in picked})
