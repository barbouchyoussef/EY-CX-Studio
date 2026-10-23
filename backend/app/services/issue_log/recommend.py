"""A second pass that proposes what to do about the issues.

Deliberately separate from generation. Asked to diagnose and prescribe in one breath, a model
biases the diagnosis toward problems with tidy fixes -- and the client's own log keeps the two
apart, with the "Findings"/"Investigation" columns carrying no remedies at all.

Runs per client over the finished log, so a recommendation can address a pattern once instead of
repeating itself down thirty rows.
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

EFFORTS = ("quick win", "medium", "major programme")

RECOMMEND_SYSTEM = """You are the lead consultant writing the recommendations that accompany a
client's issue log. You are given the finished list of issues for ONE client.

Write recommendations a client can act on. Group where grouping is honest: if eight issues all
stem from nobody owning complaint follow-up, that is ONE recommendation addressing eight issues,
not eight recommendations. If an issue needs its own distinct action, give it one.

Expect roughly one recommendation for every two to four issues.

FOR EACH RECOMMENDATION
- "action": what to do, as an imperative starting with a verb. Concrete and checkable.
  GOOD: "Assign a named owner to every complaint and publish a 48-hour first-response target"
  BAD:  "Improve complaint handling" (not an action), "Leverage synergies" (means nothing)
- "rationale": two or three plain sentences. What it fixes, and what changes for the customer or
  the business once it is done. Ordinary words, no consulting register.
- "addresses": the list of Issue # values this recommendation resolves. Use the exact numbers
  given. Never invent one.
- "effort": one of "quick win", "medium", "major programme".
    quick win        weeks, existing people, no new system
    medium           a quarter, some budget or a new process
    major programme  multi-quarter, new systems or restructuring
- "impact": "high", "medium" or "low" -- how much the customer experience actually improves.

RULES
- Base every recommendation on the issues you were given. Do not introduce new problems.
- Do not restate an issue as a recommendation. "Lack of omnichannel integration" is the problem;
  the recommendation says what to build and in what order.
- Sequence matters: if one recommendation depends on another, say so in the rationale.
- Plain text only. No markdown.

OUTPUT
Return ONLY this JSON object, no prose and no code fence:
{"recommendations": [{"action": "...", "rationale": "...", "addresses": ["1.0", "4.0"],
"effort": "quick win", "impact": "high"}]}"""


@dataclass
class RecommendRecord:
    calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    seconds: float = 0.0
    warnings: list[str] = field(default_factory=list)


def _listing(issues: Sequence[dict]) -> str:
    lines = []
    for i in issues:
        lines.append(
            f"[{i.get('issue_no')}] ({i.get('strategic_dimension')} / {i.get('sub_category')}) "
            f"[{i.get('severity')}] {i.get('finding')} — {i.get('investigation')}")
    return "\n".join(lines)


async def recommend_for_client(client: str, issues: Sequence[dict],
                               chain: Sequence[tuple[str, str]],
                               record: RecommendRecord) -> list[dict]:
    if not issues:
        return []
    user = f"CLIENT: {client}\n\nISSUES:\n{_listing(issues)}\n\nReturn the JSON object now."
    estimate = est_tokens(RECOMMEND_SYSTEM) + est_tokens(user)
    available = set(llm_client.configured_providers())

    for provider, model in [(p, m) for p, m in chain if p in available]:
        result, attempt = await guarded(
            provider, model, estimate,
            lambda p=provider, m=model: llm_client.chat(p, m, RECOMMEND_SYSTEM, user),
            is_ok=lambda c: bool(c and c.ok),
            status_of=lambda c: getattr(c, "status", 0),
            error_of=lambda c: getattr(c, "error", ""),
            label=f"recommend:{client[:30]}")
        record.calls += 1
        if result is not None:
            record.tokens_in += result.tokens_in
            record.tokens_out += result.tokens_out
            record.seconds += result.seconds
        if attempt.ok and result is not None:
            return _clean(extract_json(result.text) or {}, issues, client, record)
        logger.warning("issue_log recommend: %s/%s failed: %s", provider, model, attempt.error)

    record.warnings.append(f"{client}: recommendations unavailable")
    return []


def _clean(parsed: dict, issues: Sequence[dict], client: str,
           record: RecommendRecord) -> list[dict]:
    """Keep only recommendations that are well-formed and point at real issue numbers."""
    valid_numbers = {str(i.get("issue_no")) for i in issues}
    out: list[dict] = []
    invented = 0

    for item in parsed.get("recommendations") or []:
        if not isinstance(item, dict):
            continue
        action = strip_markdown(str(item.get("action") or ""))
        if not action:
            continue
        addresses = [str(a).strip() for a in (item.get("addresses") or [])]
        known = [a for a in addresses if a in valid_numbers]
        invented += len(addresses) - len(known)

        effort = str(item.get("effort") or "").strip().lower()
        if effort not in EFFORTS:
            effort = "medium"
        impact = str(item.get("impact") or "").strip().lower()
        if impact not in ("high", "medium", "low"):
            impact = "medium"

        out.append({
            "ref": f"R{len(out) + 1}",
            "client": client,
            "action": action,
            "rationale": strip_markdown(str(item.get("rationale") or "")) or None,
            "addresses": known,
            "issues_addressed": len(known),
            "effort": effort,
            "impact": impact,
        })

    if invented:
        record.warnings.append(
            f"{client}: {invented} recommendation link(s) pointed at issue numbers that do not "
            f"exist and were dropped.")
    return out


async def build_recommendations(issues: Sequence[dict], chain: Sequence[tuple[str, str]],
                                ) -> tuple[list[dict], RecommendRecord]:
    """One pass per client over the finished log."""
    record = RecommendRecord()
    by_client: dict[str, list[dict]] = {}
    for issue in issues:
        by_client.setdefault(str(issue.get("client") or "Client"), []).append(issue)

    out: list[dict] = []
    for client, rows in by_client.items():
        out.extend(await recommend_for_client(client, rows, chain, record))
    for n, rec in enumerate(out, 1):
        rec["ref"] = f"R{n}"
    return out, record
