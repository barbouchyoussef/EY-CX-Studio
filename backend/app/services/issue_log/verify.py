"""Deterministic checks on generated issues. No model involved -- that is the point.

The evidence quote is what makes an issue auditable, and checking it needs nothing but string
handling. Two lessons are baked in:

  1. Normalise FORMATTING before matching. A naive substring test reported 47% verification on
     desk sources; almost all the failures were the model faithfully copying markdown
     (``**Ton de voix**``) or curly quotes. The true rate was 90%.
  2. Check the NUMBERS separately. A translated quote is a prompt-compliance problem; an invented
     statistic is a credibility problem, and only the second one is dangerous. Across a 172-issue
     corpus, 99% of quoted figures were present in the source.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

Verdict = Literal["exact", "partial", "absent", "missing", "too_short"]

_MARKDOWN = re.compile(r"[*_`#>|]+")
_PUNCT = re.compile(r"[\"'“”‘’«»„<>\[\]()–—\-·•]+")
_SPACE = re.compile(r"\s+")

# A shorter quote than this cannot be matched with any confidence.
_MIN_QUOTE = 12
# Fraction of the quote that must appear contiguously to count as a partial match.
_PARTIAL_COVERAGE = 0.60


def normalise(text: str) -> str:
    """Strip formatting, unify punctuation and whitespace, casefold."""
    text = unicodedata.normalize("NFKC", text or "")
    text = _MARKDOWN.sub(" ", text)
    text = _PUNCT.sub(" ", text)
    text = text.replace(" ", " ").replace(" ", " ")
    return _SPACE.sub(" ", text).strip().casefold()


def _longest_run(needle: str, haystack: str) -> int:
    """Longest contiguous slice of `needle` present in `haystack`, by binary search on length."""
    if not needle or not haystack:
        return 0
    lo, hi, best = _MIN_QUOTE, len(needle), 0
    while lo <= hi:
        mid = (lo + hi) // 2
        step = max(1, mid // 4)
        if any(needle[i:i + mid] in haystack for i in range(0, len(needle) - mid + 1, step)):
            best, lo = mid, mid + 1
        else:
            hi = mid - 1
    return best


@dataclass
class EvidenceCheck:
    verdict: Verdict
    coverage: float          # fraction of the quote found contiguously
    numbers_total: int
    numbers_found: int

    @property
    def ok(self) -> bool:
        return self.verdict in ("exact", "partial")

    @property
    def fabricated_number(self) -> bool:
        """A figure in the quote that does not occur anywhere in the source."""
        return self.numbers_total > 0 and self.numbers_found < self.numbers_total


def check_evidence(evidence: str | None, source: str) -> EvidenceCheck:
    quote = normalise(evidence or "")
    src = normalise(source)

    nums = [n for n in re.findall(r"\d[\d.,]*", evidence or "") if len(n) > 1]
    found = sum(1 for n in nums if n in src)

    if not (evidence or "").strip():
        return EvidenceCheck("missing", 0.0, len(nums), found)
    if len(quote) < _MIN_QUOTE:
        return EvidenceCheck("too_short", 0.0, len(nums), found)
    if quote in src:
        return EvidenceCheck("exact", 1.0, len(nums), found)

    coverage = _longest_run(quote, src) / len(quote)
    verdict: Verdict = "partial" if coverage >= _PARTIAL_COVERAGE else "absent"
    return EvidenceCheck(verdict, round(coverage, 2), len(nums), found)


# --------------------------------------------------------------------------------------------
# Shape checks -- the one style metric that calibrated cleanly against the reference log
# --------------------------------------------------------------------------------------------

_MAX_FINDING_CHARS = 95


def is_sentence_shaped(finding: str) -> bool:
    """A finding should be a noun phrase. The reference log scores 0% on this; our v1 scored
    6-18%, entirely from the completeness sweep."""
    f = (finding or "").strip()
    return bool(f) and (len(f) > _MAX_FINDING_CHARS or ". " in f or f.endswith("."))


# --------------------------------------------------------------------------------------------
# Evidence that is an opinion rather than a fact
# --------------------------------------------------------------------------------------------
# Documents do not reach the issue log directly -- they are summarised into a deep dive first,
# and that summary mixes facts it observed with judgements it drew. When an issue quotes the
# judgement, it rests on the previous model's opinion and a client can check it against nothing.
# Measured on a 79-issue run: 33% of document-sourced issues quoted a judgement, against 5% for
# every other source, so this is specific to the document path.
#
# `may` is matched case-sensitively on purpose: the modal is lower-case, whereas "May" in a
# quote is nearly always the month.
_JUDGEMENT_WORDS = (
    "suggests?|suggesting|indicates?|indicating|risks?|might|could|appears?|seems?|likely|potenti"
    "al(?:ly)?|signals|signalling|flags|highlights?|underscores?|underscoring|reflects?|exposes?"
    "|offering upside|requires? careful|unless offset|typical in|we recommend|should consider"
)

_JUDGEMENT_CI = re.compile(
    r"\b(?:" + _JUDGEMENT_WORDS + r")\b",
    re.I,
)
_JUDGEMENT_CS = re.compile(r"\bmay\b")


def judgement_words(evidence: str | None) -> list[str]:
    """The opinion markers present in an evidence quote, in the order they appear.

    Empty list means the quote reads as a statement of fact. Reported rather than acted on:
    a weakly-grounded issue can still be a real one, so this marks the row instead of dropping
    it, and lets a run be measured against the previous one.
    """
    text = evidence or ""
    hits = [m.group(0) for m in _JUDGEMENT_CI.finditer(text)]
    hits += [m.group(0) for m in _JUDGEMENT_CS.finditer(text)]
    return hits


def strip_markdown(text: str) -> str:
    """Remove emphasis markers that would render as literal asterisks in a spreadsheet cell."""
    return _SPACE.sub(" ", re.sub(r"(\*{1,3}|_{2,}|`)", "", text or "")).strip()
