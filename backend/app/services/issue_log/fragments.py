"""Detect issues that are fragments of one underlying problem. No model involved.

A previous attempt at consolidation used an LLM to decide what to merge. It collapsed 518 issues
to 28 and merged findings from unrelated companies, so that pass was removed. Nothing here asks a
model anything: every decision is a string comparison over the source text, and the two decisions
are deliberately separated by how certain they are.

  TIER 1 -- MERGE.  Two issues quote the SAME words from the same chunk. There is one fact
                    underneath them, so there is one issue. This is not a judgement call.

  TIER 2 -- FLAG.   Two issues quote different words, but one issue's investigation asserts
                    figures that are only evidenced in the other's quote. That is the signature
                    of a single finding split in half, each half keeping part of the proof --
                    but "same finding" is an editorial call, so the rows are marked and left
                    alone for a human to decide.

Worked example of why the split matters. In a real 79-issue run the annual report produced:

    "Declining call handling capacity during system migration"   evidence: monthly call volumes
    "Inconsistent call handling performance across quarters"     evidence: Calls Handled % table

Both describe the Q4 degradation and the first one's investigation quotes 79.5%/74.2%, which are
evidenced only in the second. Tier 2 catches that pair. Tier 1 does not, and must not: their
quotes are different sentences, and a rule confident enough to merge them would also be confident
enough to merge things that merely share a topic.

Whatever the tiers decide, `merge_fragments` refuses to shrink a run by more than
``MAX_SHRINK``. If it would, it returns the input untouched and records a warning. A dedupe pass
that removes a third of the log is far more likely to be broken than right.
"""

from __future__ import annotations

import logging
import re
from typing import Iterable, Sequence

from app.services.issue_log import verify

logger = logging.getLogger(__name__)

# Fraction of the shorter quote that must be shared for two quotes to count as the same words.
SAME_QUOTE_OVERLAP = 0.80
# Never merge more than this many issues into one. A large group means the rule is misfiring.
MAX_GROUP = 3
# Refuse to remove more than this share of the log, whatever the rule concluded.
MAX_SHRINK = 0.20
# Figures shorter than this are too common to identify anything ("3", "10").
_MIN_FIGURE_LEN = 3

_FIGURE = re.compile(r"\d[\d.,]*%?")


def _figures(text: str | None) -> set[str]:
    """Distinctive numbers in a piece of text, normalised for comparison."""
    out: set[str] = set()
    for raw in _FIGURE.findall(text or ""):
        f = raw.rstrip(".,")
        if len(f) >= _MIN_FIGURE_LEN:
            out.add(f)
    return out


def _span(quote: str, source_norm: str) -> tuple[int, int] | None:
    """Where a quote sits in its normalised source, or None if it cannot be located."""
    q = verify.normalise(quote or "")
    if len(q) < 12 or not source_norm:
        return None
    at = source_norm.find(q)
    if at >= 0:
        return at, at + len(q)
    # Partial quotes still locate: find the longest slice that does occur, and use its position.
    for size in (len(q) * 3 // 4, len(q) // 2):
        if size < 12:
            break
        for i in range(0, len(q) - size + 1, max(1, size // 4)):
            at = source_norm.find(q[i:i + size])
            if at >= 0:
                return at, at + size
    return None


def _overlap(a: tuple[int, int], b: tuple[int, int]) -> float:
    lo, hi = max(a[0], b[0]), min(a[1], b[1])
    if hi <= lo:
        return 0.0
    return (hi - lo) / min(a[1] - a[0], b[1] - b[0])


def _merge_group(group: list[dict]) -> dict:
    """Fold a group into its most complete member. Deterministic: no wording is invented."""
    # The longest investigation is the one that did the most work; keep it as the survivor.
    group = sorted(group, key=lambda i: len(str(i.get("investigation") or "")), reverse=True)
    keeper = dict(group[0])
    order = ("critical", "high", "medium", "low")
    keeper["severity"] = min((i.get("severity", "medium") for i in group),
                             key=lambda s: order.index(s) if s in order else len(order))
    keeper["reports"] = sum(int(i.get("reports") or 1) for i in group)
    keeper["merged_from"] = [str(i.get("finding") or "") for i in group[1:]]
    return keeper


def merge_fragments(issues: Sequence[dict], chunks: Iterable, record=None) -> list[dict]:
    """Merge same-quote issues (tier 1) and mark split findings (tier 2).

    Grouping never crosses a chunk or a client, so an issue from one company's interview can
    never be folded into another company's document.
    """
    issues = [dict(i) for i in issues]
    if len(issues) < 2:
        return issues

    source_norm = {c.label: verify.normalise(c.body) for c in chunks}
    spans = [_span(str(i.get("evidence") or ""), source_norm.get(str(i.get("inspection_point")), ""))
             for i in issues]

    # ---- tier 1: identical quotes -> one issue -------------------------------------------
    parent = list(range(len(issues)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a in range(len(issues)):
        for b in range(a + 1, len(issues)):
            if spans[a] is None or spans[b] is None:
                continue
            if issues[a].get("inspection_point") != issues[b].get("inspection_point"):
                continue
            if (issues[a].get("client") or "") != (issues[b].get("client") or ""):
                continue
            if _overlap(spans[a], spans[b]) >= SAME_QUOTE_OVERLAP:
                ra, rb = find(a), find(b)
                if ra != rb:
                    parent[rb] = ra

    groups: dict[int, list[int]] = {}
    for i in range(len(issues)):
        groups.setdefault(find(i), []).append(i)

    kept: list[dict] = []
    removed = 0
    for root, members in groups.items():
        if len(members) == 1:
            kept.append(issues[members[0]])
            continue
        if len(members) > MAX_GROUP:
            # Too big to trust -- a correct rule does not find five issues on one sentence.
            logger.warning("issue_log: refusing to merge a group of %d on one quote (%r)",
                           len(members), str(issues[members[0]].get("finding"))[:60])
            kept.extend(issues[m] for m in members)
            continue
        merged = _merge_group([issues[m] for m in members])
        logger.info("issue_log: merged %d fragments into %r",
                    len(members), str(merged.get("finding"))[:60])
        kept.append(merged)
        removed += len(members) - 1

    # ---- the anti-collapse floor ----------------------------------------------------------
    if removed and removed / len(issues) > MAX_SHRINK:
        msg = (f"fragment merge would have removed {removed} of {len(issues)} issues "
               f"(> {MAX_SHRINK:.0%}); kept the original set instead")
        logger.warning("issue_log: %s", msg)
        if record is not None:
            record.warnings.append(msg)
        return issues

    if record is not None:
        record.merged_fragments = removed

    # ---- tier 2: split findings -> flag only, never merge ----------------------------------
    for a in range(len(kept)):
        fa = _figures(kept[a].get("investigation"))
        if not fa:
            continue
        ea = _figures(kept[a].get("evidence"))
        orphans = fa - ea                      # asserted but not evidenced here
        if not orphans:
            continue
        for b in range(len(kept)):
            if a == b:
                continue
            if kept[a].get("inspection_point") != kept[b].get("inspection_point"):
                continue
            if (kept[a].get("client") or "") != (kept[b].get("client") or ""):
                continue
            if orphans & _figures(kept[b].get("evidence")):
                kept[a].setdefault("fragment_of", [])
                fb = str(kept[b].get("finding") or "")
                if fb not in kept[a]["fragment_of"]:
                    kept[a]["fragment_of"].append(fb)

    for i, issue in enumerate(kept, 1):
        issue["issue_no"] = f"{i}.0"
    return kept
