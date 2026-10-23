"""Issue-log generation: sources -> per-chunk extraction -> normalisation -> a run record.

    for each source chunk (in parallel, under a per-provider token budget):
        generate  -- exhaustive extraction from THAT chunk alone
        sweep     -- one pass for anything genuinely missed (usually returns nothing)
    normalise     -- canonical keys, taxonomy resolution, exact-duplicate removal, numbering
    verify        -- evidence quotes checked against the source, deterministically

Per-chunk rather than one bundled call: given every source at once the model produces a curated
shortlist no matter how much material it has (45 issues), while the same text chunked per
document yields 141. Chunking is the single biggest lever in this pipeline.

Every stage records what it did in a RunRecord. That is what made the earlier failures findable:
a merge pass that silently collapsed 518 issues into 28, a prompt patch that never applied, an
evidence check that reported 47% because it could not see through markdown.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field, asdict
from typing import Sequence

from app.services.issue_log import fragments, prompts, taxonomy, verify
from app.services.issue_log.sources import SourceChunk, est_tokens
from app.services.llm import client as llm_client
from app.services.llm.throttle import guarded
from app.services.llm.utils import extract_json

logger = logging.getLogger(__name__)

# Ordered failover. The Mistral model follows the shared MISTRAL_MODEL setting so the issue log
# uses the same free-tier model as the rest of the application. Gemini is a fallback only.
#
# OpenAI is deliberately absent. gpt-5.4 scored best on quality per second, but a key with no
# credit answers 429 -- indistinguishable from a rate limit -- and every call then burned four
# retries with backoff before failing over. Set ISSUE_LOG_CHAIN to re-enable it once funded:
_configured_mistral_model = os.getenv("MISTRAL_MODEL", "ministral-8b-latest").strip() or "ministral-8b-latest"
_configured_gemini_model = next(
    (model.strip() for model in os.getenv("GEMINI_TEXT_MODELS", "gemini-3.5-flash").split(",") if model.strip()),
    "gemini-3.5-flash",
)

#     ISSUE_LOG_CHAIN="openai:gpt-5.4,mistral:ministral-8b-latest,gemini:gemini-3.5-flash"
DEFAULT_CHAIN: list[tuple[str, str]] = [
    ("mistral", _configured_mistral_model),
    ("gemini", _configured_gemini_model),
]


def _chain_from_env() -> list[tuple[str, str]] | None:
    raw = os.getenv("ISSUE_LOG_CHAIN", "").strip()
    if not raw:
        return None
    chain: list[tuple[str, str]] = []
    for part in raw.split(","):
        provider, _, model = part.strip().partition(":")
        if provider and model:
            chain.append((provider.strip(), model.strip()))
    return chain or None

SEVERITIES = ("critical", "high", "medium", "low")

# Which RunRecord counter each evidence verdict increments.
_EVIDENCE_COUNTERS = {"exact": "evidence_exact", "partial": "evidence_partial",
                      "absent": "evidence_absent", "missing": "evidence_missing",
                      "too_short": "evidence_missing"}

# The model occasionally renames output fields despite an explicit schema; a sweep pass once
# returned name/fact/taxonomy_dimension and every row was silently discarded. Accepting obvious
# synonyms costs nothing and stops prompt drift from deleting real issues.
_KEY_ALIASES = {
    "finding": ("finding", "name", "issue", "title", "problem", "deficiency"),
    "investigation": ("investigation", "fact", "description", "detail", "details", "explanation"),
    "evidence": ("evidence", "quote", "source_quote", "excerpt"),
    "reports": ("reports", "report_count", "mentions", "count", "customers"),
    "severity": ("severity", "priority", "impact"),
    "severity_reason": ("severity_reason", "severity_justification", "severity_rationale", "why"),
    "strategic_dimension": ("strategic_dimension", "taxonomy_dimension", "dimension", "category",
                            "main_category"),
    "sub_category": ("sub_category", "taxonomy_category", "subcategory", "sub-category"),
    "channel": ("channel", "channels"),
}


@dataclass
class ChunkRecord:
    label: str
    client: str
    mode: str
    tokens_in_source: int
    generated: int = 0
    swept: int = 0
    provider: str = ""
    model: str = ""
    retries: int = 0
    failed_over: bool = False
    tokens_in: int = 0
    tokens_out: int = 0
    seconds: float = 0.0
    error: str = ""


@dataclass
class RunRecord:
    """Everything needed to explain a run without re-running it."""
    prompt_version: str = prompts.PROMPT_VERSION
    chunks: list[ChunkRecord] = field(default_factory=list)
    raw_issues: int = 0
    dropped_no_finding: int = 0
    dropped_off_taxonomy: int = 0
    dropped_duplicate: int = 0
    evidence_exact: int = 0
    evidence_partial: int = 0
    evidence_absent: int = 0
    evidence_missing: int = 0
    fabricated_numbers: int = 0
    # Evidence that quotes the source's OPINION rather than a fact it reported. Flagged,
    # never dropped: a weakly-grounded issue can still be a real one.
    judgement_evidence: int = 0
    merged_fragments: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def calls(self) -> int:
        return len(self.chunks)

    @property
    def tokens_in(self) -> int:
        return sum(c.tokens_in for c in self.chunks)

    @property
    def tokens_out(self) -> int:
        return sum(c.tokens_out for c in self.chunks)

    def as_dict(self) -> dict:
        d = asdict(self)
        d.update(calls=self.calls, tokens_in=self.tokens_in, tokens_out=self.tokens_out)
        return d


async def _complete(system: str, user: str, chain: Sequence[tuple[str, str]],
                    record: ChunkRecord, label: str) -> str | None:
    """Try each provider in order, each inside its own budget and concurrency cap."""
    estimate = est_tokens(system) + est_tokens(user)
    available = set(llm_client.configured_providers())
    usable = [(p, m) for p, m in chain if p in available]
    if not usable:
        record.error = "no LLM provider is configured"
        return None

    for index, (provider, model) in enumerate(usable):
        result, attempt = await guarded(
            provider, model, estimate,
            lambda p=provider, m=model: llm_client.chat(p, m, system, user),
            is_ok=lambda c: bool(c and c.ok),
            status_of=lambda c: getattr(c, "status", 0),
            error_of=lambda c: getattr(c, "error", ""),
            label=label,
        )
        record.retries += attempt.retries
        if result is not None:
            record.tokens_in += result.tokens_in
            record.tokens_out += result.tokens_out
            record.seconds += result.seconds
        if attempt.ok and result is not None:
            record.provider, record.model = provider, model
            record.failed_over = index > 0
            return result.text
        record.error = attempt.error
        logger.warning("issue_log %s: %s/%s failed: %s", label, provider, model, attempt.error)
    return None


def _issues_from(text: str | None) -> list[dict]:
    if not text:
        return []
    data = extract_json(text) or {}
    return [i for i in (data.get("issues") or []) if isinstance(i, dict)]


async def _run_chunk(chunk: SourceChunk, chain: Sequence[tuple[str, str]],
                     focus: str | None, sweep: bool) -> tuple[list[dict], ChunkRecord]:
    record = ChunkRecord(label=chunk.label, client=chunk.client, mode=chunk.mode,
                         tokens_in_source=chunk.tokens)
    rendered = chunk.render()

    text = await _complete(prompts.generate_system(chunk.mode),
                           prompts.user_prompt(rendered, chunk.client, focus),
                           chain, record, f"generate:{chunk.label[:40]}")
    issues = _issues_from(text)
    record.generated = len(issues)

    if sweep and issues:
        extra_text = await _complete(
            prompts.sweep_system(chunk.mode),
            prompts.sweep_prompt(rendered, chunk.client,
                                 [str(i.get("finding", "")) for i in issues], focus),
            chain, record, f"sweep:{chunk.label[:40]}")
        extra = _issues_from(extra_text)
        record.swept = len(extra)
        issues += extra

    for issue in issues:
        issue["_label"] = chunk.label
        issue["_client"] = chunk.client
        issue["_kind"] = chunk.artifact_kind
        issue["_ref"] = chunk.artifact_ref
        issue["_mode"] = chunk.mode
    return issues, record


def _canonical(item: dict) -> dict:
    lowered = {str(k).strip().lower(): v for k, v in item.items()}
    out = {k: v for k, v in item.items() if str(k).startswith("_")}
    for canon, aliases in _KEY_ALIASES.items():
        for alias in aliases:
            if lowered.get(alias) not in (None, ""):
                out[canon] = lowered[alias]
                break
    return out


# A page number larger than this is a parse error rather than a citation; the longest
# client document seen so far runs to 28 pages.
_MAX_PAGE = 2000


def _coerce_page(value) -> int | None:
    """A page number from the model, or None.

    Accepts a bare integer or something like "p. 4"; anything else is None. A page is a
    citation a consultant will act on, so a value that cannot be read as a plain positive
    number is dropped rather than guessed at. Bounded above because a four-digit "page" is a
    parse error, not a finding -- the same reasoning as MAX_GROUP in fragments.py.
    """
    if value is None:
        return None
    text = str(value).strip()
    digits = re.search(r"(?<![-\d])\d+", text)   # a leading minus is not a page 1
    if not digits:
        return None
    page = int(digits.group())
    return page if 1 <= page <= _MAX_PAGE else None


def _coerce_reports(value) -> int:
    try:
        n = int(str(value).strip())
    except (TypeError, ValueError):
        return 1
    return max(1, n)


def normalise(raw: Sequence[dict], chunks: Sequence[SourceChunk],
              record: RunRecord) -> list[dict]:
    """Canonical keys, taxonomy resolution, exact-duplicate removal, evidence verification."""
    source_by_label = {c.label: c.body for c in chunks}
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []

    for item in raw:
        item = _canonical(item)
        finding = verify.strip_markdown(str(item.get("finding") or ""))
        investigation = verify.strip_markdown(str(item.get("investigation") or ""))

        # The model sometimes packs the whole issue into `finding` with a separator, or leaves
        # `investigation` empty. Recover rather than discard -- the content is there.
        if finding and not investigation:
            for sep in (" — ", " – ", ": "):
                if sep in finding:
                    head, tail = finding.split(sep, 1)
                    if len(tail.strip()) > 40:
                        finding, investigation = head.strip(), tail.strip()
                        break
        if finding and not investigation:
            investigation = finding

        if not finding:
            record.dropped_no_finding += 1
            continue

        dimension, sub_category = taxonomy.resolve(item.get("strategic_dimension"),
                                                   item.get("sub_category"))
        if dimension is None:
            record.dropped_off_taxonomy += 1
            logger.info("issue_log: dropped %r — unrecognised dimension %r",
                        finding[:60], item.get("strategic_dimension"))
            continue

        client = str(item.get("_client") or "")
        key = (client.casefold(), finding.casefold())
        if key in seen:
            record.dropped_duplicate += 1
            continue
        seen.add(key)

        severity = str(item.get("severity") or "").strip().lower()
        if severity not in SEVERITIES:
            severity = "medium"

        check = verify.check_evidence(item.get("evidence"),
                                      source_by_label.get(str(item.get("_label")), ""))
        counter = _EVIDENCE_COUNTERS.get(check.verdict)
        if counter:
            setattr(record, counter, getattr(record, counter) + 1)
        if check.fabricated_number:
            record.fabricated_numbers += 1

        judgement = verify.judgement_words(item.get("evidence"))
        if judgement:
            record.judgement_evidence += 1

        out.append({
            "issue_no": f"{len(out) + 1}.0",
            "finding": finding,
            "investigation": investigation,
            # Stored clean: the model copies markdown straight out of the source, so quotes
            # arrived looking like *"Ton de voix"*. Verification normalises formatting away
            # before matching, so stripping it here costs nothing and the cell stays readable.
            "evidence": verify.strip_markdown(str(item.get("evidence") or "")) or None,
            "evidence_status": check.verdict,
            "evidence_coverage": check.coverage,
            "reports": _coerce_reports(item.get("reports")),
            "severity": severity,
            "severity_reason": verify.strip_markdown(str(item.get("severity_reason") or "")) or None,
            "strategic_dimension": dimension,
            "sub_category": sub_category,
            "channel": (str(item.get("channel")).strip() or None) if item.get("channel") else None,
            "inspection_point": str(item.get("_label") or ""),
            # The document is deterministic (the chunk label above); the page is the one part
            # only the model can supply, so it is validated rather than trusted.
            "page": _coerce_page(item.get("page")),
            "client": client or None,
            "source_kind": item.get("_kind"),
            "source_ref": item.get("_ref"),
            "sentence_shaped": verify.is_sentence_shaped(finding),
            # The opinion markers found in the quote, so a reviewer can see WHY a row is
            # marked weakly grounded rather than having to take it on trust.
            "judgement_evidence": judgement or None,
        })

    return out


async def generate_issues(
    chunks: Sequence[SourceChunk],
    *,
    chain: Sequence[tuple[str, str]] | None = None,
    focus: str | None = None,
    sweep: bool = True,
    max_issues: int | None = 200,
) -> tuple[list[dict], RunRecord]:
    """Generate an issue log from prepared source chunks.

    ``max_issues`` is a guard rail, not a target: a well-formed engagement lands at 150-200, and
    a run that blows past it means a source is being split into variants rather than diagnosed.
    """
    record = RunRecord()
    usable = [c for c in chunks if c.body.strip()]
    if not usable:
        record.warnings.append("No usable material in the selected sources.")
        return [], record

    chain = list(chain or _chain_from_env() or DEFAULT_CHAIN)
    results = await asyncio.gather(*[_run_chunk(c, chain, focus, sweep) for c in usable])

    raw: list[dict] = []
    for issues, chunk_record in results:
        raw.extend(issues)
        record.chunks.append(chunk_record)
        if chunk_record.error and not chunk_record.provider:
            record.warnings.append(f"{chunk_record.label}: {chunk_record.error[:160]}")
    record.raw_issues = len(raw)

    issues = normalise(raw, usable, record)

    # Fold issues that quote the SAME words into one, and mark findings that look split across
    # two rows. Purely string comparison -- see fragments.py for why no model is involved and
    # for the floor that refuses to shrink a run by more than a fifth.
    issues = fragments.merge_fragments(issues, usable, record)

    if max_issues and len(issues) > max_issues:
        record.warnings.append(
            f"{len(issues)} issues generated; kept the first {max_issues}. A source is probably "
            f"being split into variants rather than diagnosed.")
        issues = issues[:max_issues]
        for n, issue in enumerate(issues, 1):
            issue["issue_no"] = f"{n}.0"

    if record.evidence_absent:
        record.warnings.append(
            f"{record.evidence_absent} issue(s) quote text not found in their source "
            f"(usually a translated quote; check before publishing).")
    if record.fabricated_numbers:
        record.warnings.append(
            f"{record.fabricated_numbers} issue(s) cite a figure absent from the source.")
    if record.judgement_evidence:
        record.warnings.append(
            f"{record.judgement_evidence} issue(s) quote an opinion rather than a fact; their "
            f"evidence cannot be checked against the source.")
    fragmented = sum(1 for i in issues if i.get("fragment_of"))
    if fragmented:
        record.warnings.append(
            f"{fragmented} issue(s) assert figures evidenced only in another row -- they may be "
            f"one finding split in two. Left in place; see the 'Possible fragment of' column.")

    return issues, record
