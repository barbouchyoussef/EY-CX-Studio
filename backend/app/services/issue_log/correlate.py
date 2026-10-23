"""Cross-source correlation: which issues corroborate each other, and which conflict.

Generation reads every source in isolation, which is deliberate -- it is what makes each source
an honest witness. Two stakeholders independently reporting the same gap is real evidence; if the
second had been shown the first's answers, agreement would prove nothing. The cost of that
isolation is that nothing in the pipeline notices when two sources agree, or when they flatly
contradict each other.

This pass runs after generation, per client, over the finished log. It is deliberately the
weakest possible kind of step:

    IT MAY ONLY ADD FIELDS. It never merges rows, never deletes rows, never rewrites text.

That constraint is not stylistic. A previous pass that was allowed to remove rows collapsed a
518-issue log into 28 thematic buckets, and a hardened version still tried to drop a client's
entire log. A pass that can only annotate has a worst case of a wrong label, which a consultant
reads and ignores.

Two annotations are produced:

    corroboration -- the same deficiency reported independently by 2+ sources. The issue keeps
                     its own wording and gains `corroborated_by`, so the consultant can say "three
                     people told us this" instead of "someone mentioned this".
    conflict      -- two sources make claims that cannot both be true. Not a duplicate and not a
                     nuance: a factual disagreement a consultant must resolve before publishing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Sequence

from app.services.issue_log.sources import est_tokens
from app.services.issue_log.verify import strip_markdown
from app.services.llm import client as llm_client
from app.services.llm.throttle import guarded
from app.services.llm.utils import extract_json

logger = logging.getLogger(__name__)

# Beyond this many issues the listing stops fitting a single call comfortably and the model
# starts losing track of indices. Larger logs are correlated in batches of this size.
BATCH_SIZE = 120

# A "corroboration" naming more sources than a client actually has is a parse error, not a
# finding. Bounded defensively.
MAX_GROUP = 8


CORRELATE_SYSTEM = """You are the lead consultant reviewing an issue log before it goes to the
client. Each issue was written by a different analyst who read ONE source and did not see the
others. Your job is to compare them.

You will receive every issue for one client as a numbered list:
    [index] (dimension) SOURCE: <where it came from> | finding — investigation

Find two things, and ONLY these two.

1. CORROBORATION -- the same deficiency reported independently by DIFFERENT sources.
   This is the valuable one. When a CEO interview and a customer-review analysis both describe
   complaints going unanswered, that is far stronger evidence than either alone.
   - The sources must be DIFFERENT. Two issues from the same source are not corroboration.
   - It must be the SAME deficiency, not the same topic. "No owner for customer issues" and
     "No budget for customer fixes" are both governance, but they are different problems.
   - Group every index that reports it. Choose as "primary" the index whose wording is clearest.

2. CONFLICT -- two sources make factual claims that CANNOT BOTH BE TRUE.
   This is rarer and matters more, because publishing both would embarrass the client.
   - A real conflict: one source says the call centre has access to customer segments, another
     says it has none. One says a journey map was updated in March, another says nobody owns
     updating it.
   - NOT a conflict: two sources describing different parts of a problem, or the same problem
     with different emphasis, or one being more critical than the other. Different perspectives
     are normal and healthy. Only flag a genuine factual disagreement.
   - Say plainly what each side claims, in one short sentence each.

RULES
- Report only what the issues in front of you support. Do not infer beyond them.
- Be conservative on conflicts. A false conflict wastes a consultant's time chasing nothing; a
  handful of solid ones is worth more than a long speculative list.
- Most issues will be in neither group. That is the normal outcome. Empty lists are fine.
- Never propose deleting, merging or rewriting an issue. You are annotating, not editing.
- Plain text. No markdown.

OUTPUT
Return ONLY this JSON object, no prose and no code fence:
{"corroborations": [{"primary": <index>, "also": [<index>, ...], "what": "one sentence naming the
shared deficiency"}],
 "conflicts": [{"a": <index>, "b": <index>, "a_claims": "...", "b_claims": "...",
 "why_it_matters": "one sentence"}]}"""


@dataclass
class CorrelateRecord:
    calls: int = 0
    batches: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    seconds: float = 0.0
    corroborated_issues: int = 0
    corroboration_groups: int = 0
    conflicts: int = 0
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "calls": self.calls, "batches": self.batches,
            "tokens_in": self.tokens_in, "tokens_out": self.tokens_out,
            "seconds": round(self.seconds, 1),
            "corroborated_issues": self.corroborated_issues,
            "corroboration_groups": self.corroboration_groups,
            "conflicts": self.conflicts,
            "warnings": self.warnings,
        }


def _listing(issues: Sequence[dict], offset: int = 0) -> str:
    """Compact rendering. The source label is the point -- without it the model cannot tell
    independent agreement from one analyst repeating themselves."""
    lines = []
    for n, issue in enumerate(issues):
        source = (issue.get("inspection_point") or "unknown source")[:52]
        lines.append(
            f"[{n + offset}] ({issue.get('strategic_dimension')}) SOURCE: {source} | "
            f"{issue.get('finding')} — {issue.get('investigation')}")
    return "\n".join(lines)


async def _call(system: str, user: str, chain: Sequence[tuple[str, str]],
                record: CorrelateRecord, label: str) -> str | None:
    estimate = est_tokens(system) + est_tokens(user)
    available = set(llm_client.configured_providers())
    for provider, model in [(p, m) for p, m in chain if p in available]:
        result, attempt = await guarded(
            provider, model, estimate,
            lambda p=provider, m=model: llm_client.chat(p, m, system, user),
            is_ok=lambda c: bool(c and c.ok),
            status_of=lambda c: getattr(c, "status", 0),
            error_of=lambda c: getattr(c, "error", ""),
            label=label)
        record.calls += 1
        if result is not None:
            record.tokens_in += result.tokens_in
            record.tokens_out += result.tokens_out
            record.seconds += result.seconds
        if attempt.ok and result is not None:
            return result.text
        logger.warning("issue_log correlate: %s/%s failed: %s", provider, model, attempt.error)
    return None


def _apply(issues: list[dict], parsed: dict, offset: int,
           record: CorrelateRecord) -> list[dict]:
    """Attach annotations. Returns the conflicts found; issues are annotated in place.

    Every index is bounds-checked and every group is validated to span more than one source --
    the model occasionally "corroborates" two issues from the same document, which is just a
    duplicate and says nothing about agreement.
    """
    total = len(issues)

    def resolve(raw) -> int | None:
        try:
            idx = int(raw) - offset
        except (TypeError, ValueError):
            return None
        return idx if 0 <= idx < total else None

    for group in parsed.get("corroborations") or []:
        if not isinstance(group, dict):
            continue
        primary = resolve(group.get("primary"))
        if primary is None:
            continue
        members = [primary]
        for raw in (group.get("also") or [])[:MAX_GROUP]:
            idx = resolve(raw)
            if idx is not None and idx not in members:
                members.append(idx)
        if len(members) < 2:
            continue

        sources = {str(issues[i].get("inspection_point") or "") for i in members}
        if len(sources) < 2:
            continue                      # same source twice is a duplicate, not agreement

        shared = strip_markdown(str(group.get("what") or "")) or None
        for i in members:
            issues[i]["corroborated_by"] = sorted(s for s in sources if s)
            issues[i]["corroboration_count"] = len(sources)
            issues[i]["corroborates"] = shared
            issues[i]["is_primary_report"] = (i == primary)
        record.corroborated_issues += len(members)
        record.corroboration_groups += 1

    conflicts: list[dict] = []
    for item in parsed.get("conflicts") or []:
        if not isinstance(item, dict):
            continue
        a, b = resolve(item.get("a")), resolve(item.get("b"))
        if a is None or b is None or a == b:
            continue
        source_a = str(issues[a].get("inspection_point") or "")
        source_b = str(issues[b].get("inspection_point") or "")
        if source_a == source_b:
            continue                      # one source disagreeing with itself is not a conflict

        conflict = {
            "ref": f"C{len(conflicts) + 1}",
            "issue_a": issues[a].get("issue_no"),
            "issue_b": issues[b].get("issue_no"),
            "source_a": source_a,
            "source_b": source_b,
            "a_claims": strip_markdown(str(item.get("a_claims") or "")),
            "b_claims": strip_markdown(str(item.get("b_claims") or "")),
            "why_it_matters": strip_markdown(str(item.get("why_it_matters") or "")) or None,
        }
        conflicts.append(conflict)
        for idx, other in ((a, b), (b, a)):
            issues[idx].setdefault("conflicts_with", []).append(issues[other].get("issue_no"))
            issues[idx]["has_conflict"] = True
    record.conflicts += len(conflicts)
    return conflicts


async def correlate(issues: list[dict], chain: Sequence[tuple[str, str]],
                    ) -> tuple[list[dict], CorrelateRecord]:
    """Annotate a finished log with corroborations and conflicts, per client.

    The issue list is mutated in place with additional fields only. Returns the conflicts, which
    the UI and the workbook surface separately -- they are a reviewer's to-do list, not rows.
    """
    record = CorrelateRecord()
    if len(issues) < 2:
        return [], record

    by_client: dict[str, list[dict]] = {}
    for issue in issues:
        by_client.setdefault(str(issue.get("client") or "Client"), []).append(issue)

    all_conflicts: list[dict] = []
    for client, rows in by_client.items():
        distinct_sources = {str(r.get("inspection_point") or "") for r in rows}
        if len(distinct_sources) < 2:
            # Nothing to correlate: one source cannot corroborate or contradict itself.
            continue

        for start in range(0, len(rows), BATCH_SIZE):
            batch = rows[start:start + BATCH_SIZE]
            if len(batch) < 2:
                continue
            record.batches += 1
            user = (f"CLIENT: {client}\n\nISSUES:\n{_listing(batch, offset=start)}\n\n"
                    f"Return the JSON object now.")
            text = await _call(CORRELATE_SYSTEM, user, chain, record,
                               f"correlate:{client[:28]}")
            if not text:
                record.warnings.append(f"{client}: cross-source correlation unavailable")
                continue
            all_conflicts.extend(_apply(batch, extract_json(text) or {}, start, record))

    for n, conflict in enumerate(all_conflicts, 1):
        conflict["ref"] = f"C{n}"
    return all_conflicts, record
