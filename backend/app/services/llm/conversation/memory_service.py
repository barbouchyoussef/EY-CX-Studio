"""The running summary of what a client has already told us, per axis.

An assessment is a long conversation, and the model cannot be handed all of it on every turn. So
each axis carries a compact summary that is updated as answers arrive, and that summary is what
later questions are composed against.

It is what stops the diagnostic asking something the client already answered ten turns ago -- the
single most damaging thing a consultant-facing chat can do, because it reads as not listening.

Deliberately short. `clean_memory_text` caps it at eight lines: a summary that grows with the
conversation would defeat the purpose of having one.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable

from app.core.config import Settings

logger = logging.getLogger(__name__)


class MemoryService:
    """Axis memory updater for compact conversational state."""

    _ALLOWED_FACT_TYPES = {
        "owner",
        "tool",
        "channel",
        "cadence",
        "metric",
        "process",
        "absence",
        "outcome",
    }

    def __init__(
        self,
        settings: Settings,
        chat_messages: Callable[[list[dict[str, str]]], Awaitable[str]],
        clean_memory_text: Callable[[str | None], str],
    ) -> None:
        self.settings = settings
        self._chat_messages = chat_messages
        self._clean_memory_text = clean_memory_text

    async def update_axis_memory(
        self,
        axis: str,
        current_summary: str | None,
        new_answer: str,
        covered_labels: list[str],
    ) -> str:
        if not self.settings.mistral_api_key:
            logger.error("Cannot update axis memory with LLM because MISTRAL_API_KEY is not set.")
            return (current_summary or "").strip()

        messages = self._build_memory_update_messages(axis, current_summary, new_answer, covered_labels)
        try:
            text = await self._chat_messages(messages)
        except Exception as exc:
            logger.error("LLM memory update failed: %s", exc, exc_info=True)
            return (current_summary or "").strip()
        cleaned = self._clean_memory_text(text) or (current_summary or "").strip()
        return self._enforce_memory_labels(
            memory_text=cleaned,
            current_summary=current_summary,
            covered_labels=covered_labels,
        )

    def _build_memory_update_messages(
        self,
        axis: str,
        current_summary: str | None,
        new_answer: str,
        covered_labels: list[str],
    ) -> list[dict[str, str]]:
        covered = "\n".join(f"- {label}" for label in covered_labels[:12]) or "- (none)"
        user = (
            f"Axis: {axis}\n\n"
            f"Current memory:\n{(current_summary or '').strip()}\n\n"
            f"User answer:\n{new_answer}\n\n"
            f"Newly covered criteria labels:\n{covered}\n\n"
            "Return updated memory:"
        )
        system = (
            "You maintain a compact, highly actionable memory for a CX assessment axis.\n"
            "Update the memory with new facts from the user's answer.\n"
            "CRITICAL: You MUST explicitly extract and retain any of the following if mentioned:\n"
            "- Tools, software, or channels (e.g., Salesforce, Excel, CRM, email, Jira).\n"
            "- Specific roles, titles, or departments (e.g., CX Lead, IT Manager, Store Director).\n"
            "- Rhythms, cadences, or frequencies (e.g., weekly, monthly, ad hoc).\n"
            "- Explicit absences of process (e.g., 'no formal KPIs', 'we don't track this').\n"
            "Keep it short (max 8 lines), factual, no fluff.\n"
            "Format each fact as one semi-structured line using this shape exactly: - capability: <label> | <type>: <fact>\n"
            "Allowed <type> values: owner, tool, channel, cadence, metric, process, absence, outcome.\n"
            "CRITICAL: 'Newly covered criteria labels' contains canonical capability labels from the database. Reuse those labels exactly as written. Do not paraphrase, shorten, translate, or invent capability labels.\n"
            "If a fact clearly belongs to one of the provided labels, you MUST use that exact label.\n"
            "If no provided label clearly applies, use exactly: capability: General\n"
            "Prefer one fact per line. Do not combine multiple unrelated facts in the same line.\n"
            "Keep existing valid lines unless the new answer corrects or replaces them.\n"
            "Examples:\n"
            "- capability: Complaint follow-up | owner: CX Lead\n"
            "- capability: Complaint follow-up | cadence: weekly\n"
            "- capability: KPI tracking | absence: no formal KPI tracked\n"
            "Return only the updated memory text, no markdown."
        )
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    def _enforce_memory_labels(
        self,
        memory_text: str,
        current_summary: str | None,
        covered_labels: list[str],
    ) -> str:
        lines = [line.strip() for line in str(memory_text or "").split("\n") if line.strip()]
        if not lines:
            return ""

        allowed_labels = {
            label.strip()
            for label in covered_labels
            if str(label or "").strip()
        }
        allowed_labels.add("General")
        allowed_labels.update(self._extract_capability_labels(current_summary or ""))

        normalized_lines: list[str] = []
        seen_lines: set[str] = set()
        sole_covered_label = covered_labels[0].strip() if len(covered_labels) == 1 and covered_labels[0].strip() else None
        fallback_label = sole_covered_label or self._single_existing_non_general_label(current_summary)
        for line in lines[:8]:
            match = re.match(r"^-\s*capability:\s*(.*?)\s*\|\s*([a-z]+)\s*:\s*(.+)$", line, flags=re.IGNORECASE)
            if not match:
                if line not in seen_lines:
                    normalized_lines.append(line)
                    seen_lines.add(line)
                continue

            capability_label = match.group(1).strip()
            fact_type = self._normalize_fact_type(match.group(2).strip().lower(), match.group(3).strip())
            fact_value = match.group(3).strip()
            if not fact_value:
                continue
            if capability_label not in allowed_labels:
                capability_label = fallback_label or "General"
            elif capability_label == "General" and fallback_label:
                capability_label = fallback_label

            normalized = f"- capability: {capability_label} | {fact_type}: {fact_value}"
            dedupe_key = normalized.lower()
            if dedupe_key in seen_lines:
                continue
            normalized_lines.append(normalized)
            seen_lines.add(dedupe_key)

        return "\n".join(normalized_lines).strip()

    def _extract_capability_labels(self, memory_text: str) -> set[str]:
        labels: set[str] = set()
        for line in str(memory_text or "").split("\n"):
            match = re.match(r"^-\s*capability:\s*(.*?)\s*\|", line.strip(), flags=re.IGNORECASE)
            if match:
                labels.add(match.group(1).strip())
        return labels

    def _single_existing_non_general_label(self, memory_text: str | None) -> str | None:
        labels = {
            label
            for label in self._extract_capability_labels(memory_text or "")
            if label and label != "General"
        }
        if len(labels) == 1:
            return next(iter(labels))
        return None

    def _normalize_fact_type(self, fact_type: str, fact_value: str) -> str:
        normalized_type = str(fact_type or "").strip().lower()
        if normalized_type in self._ALLOWED_FACT_TYPES:
            return normalized_type

        value = str(fact_value or "").strip().lower()
        if not value:
            return "process"
        if any(marker in value for marker in ("no ", "not ", "none", "without ", "lack of", "don't", "do not")):
            return "absence"
        if any(marker in value for marker in ("weekly", "monthly", "daily", "quarterly", "annually", "ad hoc")):
            return "cadence"
        if any(marker in value for marker in ("email", "phone", "call", "survey", "whatsapp", "chat")):
            return "channel"
        if any(marker in value for marker in ("crm", "excel", "jira", "trello", "dashboard", "backlog", "tool", "system")):
            return "tool"
        if any(marker in value for marker in ("owner", "lead", "manager", "team", "director")):
            return "owner"
        if any(marker in value for marker in ("nps", "kpi", "csat", "complaint volume", "metric", "measure")):
            return "metric"
        if any(marker in value for marker in ("improve", "reduced", "faster", "better", "higher", "lower")):
            return "outcome"
        return "process"


def build_memory_service(
    settings: Settings,
    chat_messages: Callable[[list[dict[str, str]]], Awaitable[str]],
    clean_memory_text: Callable[[str | None], str],
) -> MemoryService:
    return MemoryService(
        settings=settings,
        chat_messages=chat_messages,
        clean_memory_text=clean_memory_text,
    )
