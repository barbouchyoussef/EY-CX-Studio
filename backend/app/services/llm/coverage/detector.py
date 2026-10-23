"""Deciding which assessment criteria an answer actually covers.

The diagnostic asks about one capability at a time, but a client rarely answers about only one --
a sentence about weekly complaint reviews speaks to several criteria at once. This service reads
an answer against the criteria in play and reports which of them it evidences, with the quote that
supports each.

Two things happen before the model is asked. A clearly negative answer ("we don't do that")
resolves deterministically, because it covers the criterion just as definitively as a positive one
and does not need interpreting. And the criteria are passed with their maturity rubrics, so the
model is judging against the framework's own wording rather than its idea of what good looks like.

`covered` is an allow-list: only ids that were actually offered come back, so a hallucinated id
cannot reach the score.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable

from pydantic import BaseModel, Field, ValidationError

from app.core.config import Settings
from app.services.llm.prompts import COVERAGE_SYSTEM_PROMPT, COVERAGE_USER_TEMPLATE

logger = logging.getLogger(__name__)


class _CoveredCriterionItem(BaseModel):
    criterion_id: int
    maturity_level_id: int | None = Field(default=None, ge=1)
    confidence: float = Field(ge=0.0, le=1.0)
    is_specific_and_actionable: bool = Field(
        description=(
    "True if the evidence contains a concrete and coherent business signal such as a tool, role, owner, "
    "channel, meeting, cadence, process, metric, document, tracker, backlog, dashboard, customer issue, "
    "decision, action, outcome, or explicit absence of process. False only when the answer is social talk, "
    "gibberish, filler text, or disconnected words with no meaningful business relation."
)

    )
    evidence: str | None = None
    rationale: str | None = None


class _CoverageResponse(BaseModel):
    covered_criteria: list[_CoveredCriterionItem] = Field(default_factory=list)


class CoverageDetectorService:
    """Semantic coverage detection with anti-loop handling."""

    def __init__(
        self,
        settings: Settings,
        chat_messages: Callable[[list[dict[str, str]]], Awaitable[str]],
        extract_json: Callable[[str], dict | None],
        is_negative_evidence_answer: Callable[[str], bool],
    ) -> None:
        self.settings = settings
        self._chat_messages = chat_messages
        self._extract_json = extract_json
        self._is_negative_evidence_answer = is_negative_evidence_answer

    async def detect_coverage(
        self,
        answer: str,
        criteria: list[dict],
        rubrics_by_capability: dict[int, list[dict]] | None = None,
    ) -> dict:
        rubrics = rubrics_by_capability or {}
        negative_evidence_coverage = self._build_negative_evidence_coverage(
            answer=answer,
            criteria=criteria,
            rubrics_by_capability=rubrics,
        )
        if negative_evidence_coverage is not None:
            return negative_evidence_coverage

        if not self.settings.mistral_api_key:
            logger.error("Cannot detect coverage because MISTRAL_API_KEY is not set.")
            return {"covered": [], "confidence": None, "evidence_by_id": {}, "rationale_by_id": {}}

        allowed_ids = {int(c["id"]) for c in criteria if "id" in c}
        maturity_level_number_lookup = self._build_maturity_level_number_lookup(rubrics)
        messages = self._build_coverage_messages(answer=answer, criteria=criteria, rubrics_by_capability=rubrics)

        parsed: _CoverageResponse | None = None
        invalid_output = ""
        for attempt in range(2):
            try:
                invalid_output = await self._chat_messages(messages)
            except Exception as exc:
                logger.error("LLM coverage detection failed on attempt %s: %s", attempt + 1, exc, exc_info=True)
                break

            parsed = self._parse_coverage_json(invalid_output)
            if parsed is not None:
                break

            logger.error("LLM coverage detection returned invalid JSON on attempt %s: %r", attempt + 1, invalid_output)
            messages = self._build_coverage_fix_messages(
                answer=answer,
                criteria=criteria,
                rubrics_by_capability=rubrics,
                invalid_output=invalid_output,
            )

        if parsed is None:
            return {"covered": [], "confidence": None, "evidence_by_id": {}, "rationale_by_id": {}}

        covered_ids: list[int] = []
        maturity_level_by_id: dict[int, int] = {}
        maturity_level_number_by_id: dict[int, int] = {}
        confidence_by_id: dict[int, float] = {}
        evidence_by_id: dict[int, str] = {}
        rationale_by_id: dict[int, str] = {}
        is_specific_and_actionable_by_id: dict[int, bool] = {}
        confidences: list[float] = []

        for item in parsed.covered_criteria:
            criterion_id = int(item.criterion_id)
            if criterion_id not in allowed_ids:
                continue
            covered_ids.append(criterion_id)
            if item.maturity_level_id is not None:
                maturity_level_id = int(item.maturity_level_id)
                maturity_level_by_id[criterion_id] = maturity_level_id
                maturity_level_number_by_id[criterion_id] = maturity_level_number_lookup.get(
                    maturity_level_id,
                    maturity_level_id,
                )
            confidence_by_id[criterion_id] = float(item.confidence)
            if item.evidence:
                evidence_by_id[criterion_id] = item.evidence
            if item.rationale:
                rationale_by_id[criterion_id] = item.rationale
            is_specific_and_actionable_by_id[criterion_id] = bool(item.is_specific_and_actionable)
            confidences.append(float(item.confidence))

        avg_confidence = (sum(confidences) / len(confidences)) if confidences else None
        return {
            "covered": covered_ids,
            "maturity_level_by_id": maturity_level_by_id,
            "maturity_level_number_by_id": maturity_level_number_by_id,
            "confidence_by_id": confidence_by_id,
            "confidence": avg_confidence,
            "evidence_by_id": evidence_by_id,
            "rationale_by_id": rationale_by_id,
            "is_specific_and_actionable_by_id": is_specific_and_actionable_by_id,
        }

    def _build_negative_evidence_coverage(
        self,
        answer: str,
        criteria: list[dict],
        rubrics_by_capability: dict[int, list[dict]],
    ) -> dict | None:
        if not self._is_negative_evidence_answer(answer):
            return None
        if not self._is_generic_negative_evidence_answer(answer):
            return None

        criterion = self._select_primary_criterion_for_negative_evidence(criteria)
        if criterion is None:
            return None

        criterion_id = int(criterion["id"])
        maturity_level_id = self._level_one_maturity_level_id(
            criterion_id=criterion_id,
            rubrics_by_capability=rubrics_by_capability,
        )
        confidence = self.settings.scoring_default_confidence_if_covered
        answer_excerpt = self._compact_answer_excerpt(answer)
        evidence = f"User explicitly stated lack of knowledge or process: {answer_excerpt}"
        rationale = (
            "The user explicitly stated they do not know, have no answer, or lack the process; "
            "this is recorded transparently as Level 1 maturity evidence for the current capability."
        )
        return {
            "covered": [criterion_id],
            "maturity_level_by_id": {criterion_id: maturity_level_id},
            "maturity_level_number_by_id": {criterion_id: 1},
            "confidence_by_id": {criterion_id: confidence},
            "confidence": confidence,
            "evidence_by_id": {criterion_id: evidence},
            "rationale_by_id": {criterion_id: rationale},
            "is_specific_and_actionable_by_id": {criterion_id: True},
        }

    def _is_generic_negative_evidence_answer(self, answer: str) -> bool:
        normalized = self._normalize_business_text(answer)
        if not normalized:
            return True

        tokens = re.findall(r"[a-z0-9]+", normalized)
        important_terms = self._important_terms(normalized)
        if len(tokens) <= 8 and len(important_terms) <= 2:
            return True
        if len(tokens) <= 5:
            return True
        return False

    def _compact_answer_excerpt(self, answer: str) -> str:
        value = " ".join(str(answer or "").strip().split())
        if not value:
            return "no answer provided"
        if len(value) <= 160:
            return f'"{value}"'
        return f'"{value[:157].rstrip()}..."'

    def _select_primary_criterion_for_negative_evidence(self, criteria: list[dict]) -> dict | None:
        eligible = [
            criterion
            for criterion in criteria
            if criterion.get("id") is not None and not criterion.get("covered")
        ]
        if not eligible:
            eligible = [criterion for criterion in criteria if criterion.get("id") is not None]
        if not eligible:
            return None
        eligible.sort(
            key=lambda criterion: (
                int(criterion.get("sort_order") or 9999),
                str(criterion.get("label") or ""),
            )
        )
        return eligible[0]

    def _level_one_maturity_level_id(
        self,
        criterion_id: int,
        rubrics_by_capability: dict[int, list[dict]],
    ) -> int:
        for rubric in rubrics_by_capability.get(criterion_id) or []:
            if int(rubric.get("maturity_level_number") or rubric.get("maturity_level_id") or 0) == 1:
                return int(rubric.get("maturity_level_id") or 1)
        for rubrics in rubrics_by_capability.values():
            for rubric in rubrics or []:
                if int(rubric.get("maturity_level_number") or rubric.get("maturity_level_id") or 0) == 1:
                    return int(rubric.get("maturity_level_id") or 1)
        return 1

    def _build_coverage_messages(
        self,
        answer: str,
        criteria: list[dict],
        rubrics_by_capability: dict[int, list[dict]],
    ) -> list[dict[str, str]]:
        criteria_blocks: list[str] = []
        for index, criterion in enumerate(criteria[:50]):
            focus_flag = "primary_focus" if index == 0 else "secondary_candidate"
            criteria_blocks.append(
                "\n".join(
                    [
                        f"- id={criterion['id']} ({focus_flag})",
                        f"  label: {criterion.get('label') or 'not provided'}",
                        f"  description: {criterion.get('description') or 'not provided'}",
                        f"  expected_evidence_examples: {criterion.get('expected_evidence') or 'not provided'}",
                        f"  question_guidance: {criterion.get('question_guidelines') or 'not provided'}",
                    ]
                )
            )
        criteria_lines = "\n".join(criteria_blocks)
        rubric_lines: list[str] = []
        for criterion in criteria[:50]:
            criterion_id = int(criterion["id"])
            for rubric in rubrics_by_capability.get(criterion_id) or []:
                rubric_lines.append(
                    f"- capability_id={criterion_id} "
                    f"maturity_level_id={rubric.get('maturity_level_id')} "
                    f"level_number={rubric.get('maturity_level_number') or rubric.get('maturity_level_id')}: "
                    f"{rubric.get('description')}"
                )

        user = COVERAGE_USER_TEMPLATE.format(
            criteria_lines=criteria_lines,
            rubrics_lines=("\n".join(rubric_lines) if rubric_lines else "- (none provided)"),
            answer=answer,
        )
        return [{"role": "system", "content": COVERAGE_SYSTEM_PROMPT}, {"role": "user", "content": user}]

    def _build_maturity_level_number_lookup(self, rubrics_by_capability: dict[int, list[dict]]) -> dict[int, int]:
        lookup: dict[int, int] = {}
        for rubrics in rubrics_by_capability.values():
            for rubric in rubrics or []:
                maturity_level_id = rubric.get("maturity_level_id")
                if maturity_level_id is None:
                    continue
                lookup[int(maturity_level_id)] = int(rubric.get("maturity_level_number") or maturity_level_id)
        return lookup

    def _build_coverage_fix_messages(
        self,
        answer: str,
        criteria: list[dict],
        rubrics_by_capability: dict[int, list[dict]],
        invalid_output: str,
    ) -> list[dict[str, str]]:
        messages = self._build_coverage_messages(answer, criteria, rubrics_by_capability)
        messages.append(
            {
                "role": "user",
                "content": (
                    "Your previous response was invalid.\n"
                    "Return only valid JSON matching the schema exactly.\n"
                    "Do not include markdown, code fences, or extra keys.\n"
                    f"Invalid output:\n{invalid_output}"
                ),
            }
        )
        return messages

    def _parse_coverage_json(self, text: str) -> _CoverageResponse | None:
        blob = self._extract_json(text)
        if not isinstance(blob, dict):
            return None
        try:
            return _CoverageResponse.model_validate(blob)
        except ValidationError as exc:
            logger.error("Coverage JSON schema validation failed: %s", exc, exc_info=True)
            return None

    def _normalize_business_text(self, value: str) -> str:
        normalized = re.sub(r"[^\w\s/-]", " ", str(value or "").lower())
        return re.sub(r"\s+", " ", normalized).strip()

    def _important_terms(self, value: str) -> set[str]:
        stopwords = {
            "and",
            "the",
            "for",
            "with",
            "from",
            "that",
            "this",
            "how",
            "what",
            "when",
            "where",
            "which",
            "customer",
            "customers",
            "issue",
            "issues",
            "feedback",
            "process",
            "team",
            "teams",
            "have",
            "has",
            "had",
            "not",
            "dont",
            "doesnt",
            "didnt",
            "know",
            "none",
            "really",
            "formal",
        }
        tokens = re.findall(r"[a-z0-9]+", self._normalize_business_text(value))
        return {
            token
            for token in tokens
            if len(token) >= 3 and token not in stopwords
        }


def build_coverage_detector_service(
    settings: Settings,
    chat_messages: Callable[[list[dict[str, str]]], Awaitable[str]],
    extract_json: Callable[[str], dict | None],
    is_negative_evidence_answer: Callable[[str], bool],
) -> CoverageDetectorService:
    return CoverageDetectorService(
        settings=settings,
        chat_messages=chat_messages,
        extract_json=extract_json,
        is_negative_evidence_answer=is_negative_evidence_answer,
    )
