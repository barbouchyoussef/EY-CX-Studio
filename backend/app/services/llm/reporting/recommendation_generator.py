"""Turning a scored capability into something the client can act on.

Two shapes, because the cost profile differs. A single-capability call is for regenerating one
recommendation on demand; the batched call covers several at once for a full report, which is what
makes a report affordable.

The rules about when a capability deserves a recommendation at all -- enough evidence, enough
confidence -- are not here. They live in the assessment's recommendation service, which decides
what to send; this module writes what it is given.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.core.config import Settings
from app.services.llm.prompts import (
    BATCH_RECOMMENDATION_SYSTEM_PROMPT,
    BATCH_RECOMMENDATION_USER_TEMPLATE,
    RECOMMENDATION_SYSTEM_PROMPT,
    RECOMMENDATION_USER_TEMPLATE,
    language_directive,
)

logger = logging.getLogger(__name__)


class BatchRecommendationItem(BaseModel):
    capability_id: int
    status: str = Field(pattern="^(ok|needs_clarification)$")
    title: str | None = None
    why_this: str | None = None
    evidence_used: str | None = None
    primary_action: str | None = None
    secondary_action: str | None = None
    expected_impact: str | None = None
    clarification_question: str | None = None


class BatchRecommendationResponse(BaseModel):
    results: list[BatchRecommendationItem] = Field(default_factory=list)


class RecommendationGeneratorService:
    """Recommendation generation (single and batch)."""

    def __init__(
        self,
        settings: Settings,
        chat_messages: Callable[[list[dict[str, str]]], Awaitable[str]],
        clean_text: Callable[[str | None], str],
        extract_json: Callable[[str], dict | None],
    ) -> None:
        self.settings = settings
        self._chat_messages = chat_messages
        self._clean_text = clean_text
        self._extract_json = extract_json

    async def generate_recommendation(
        self,
        axis: str,
        capability: str,
        maturity_label: str,
        confidence: float | None,
        justification: str | None,
        recommendation_guideline: str | None,
        priority_hint: str | None,
        business_impact: str | None,
        tone_hint: str | None,
        supporting_notes: str | None = None,
        language: str = "fr",
    ) -> str:
        is_french = (language or "").lower().startswith("fr")
        fallback_msg = "Aucune recommandation disponible pour le moment." if is_french else "No recommendation available yet."
        fallback_parts = [
            (recommendation_guideline or "").strip(),
            (business_impact or "").strip(),
        ]
        fallback = " ".join(part for part in fallback_parts if part).strip() or fallback_msg


        if not self.settings.mistral_api_key:
            logger.error("Cannot generate recommendation because MISTRAL_API_KEY is not set.")
            return fallback

        user = RECOMMENDATION_USER_TEMPLATE.format(
            axis=axis,
            capability=capability,
            maturity_label=maturity_label,
            confidence=f"{confidence:.2f}" if confidence is not None else "n/a",
            justification=(justification or "n/a"),
            recommendation_guideline=(recommendation_guideline or "n/a"),
            priority_hint=(priority_hint or "n/a"),
            business_impact=(business_impact or "n/a"),
            tone_hint=(tone_hint or "balanced"),
            supporting_notes=(supporting_notes or "n/a"),
        )
        try:
            text = await self._chat_messages(
                [{"role": "system", "content": RECOMMENDATION_SYSTEM_PROMPT + language_directive(language)}, {"role": "user", "content": user}]
            )
        except Exception as exc:
            logger.error("LLM recommendation generation failed: %s", exc, exc_info=True)
            return fallback
        return self._clean_text(text) or fallback

    async def generate_recommendations_batch(
        self,
        assessment_id: int,
        items: list[dict[str, Any]],
        language: str = "en",
        max_actions_per_capability: int | None = None,
        tone: str = "practical",
        max_words_per_capability: int | None = None,
    ) -> dict[int, dict[str, Any]]:
        if not items:
            return {}
        if not self.settings.mistral_api_key:
            logger.error("Cannot generate batch recommendations because MISTRAL_API_KEY is not set.")
            return {}
        max_actions_per_capability = max_actions_per_capability or self.settings.MAX_ACTIONS_PER_CAPABILITY
        max_words_per_capability = max_words_per_capability or self.settings.MAX_WORDS_PER_CAPABILITY

        user = BATCH_RECOMMENDATION_USER_TEMPLATE.format(
            assessment_id=assessment_id,
            language=language,
            max_actions=max_actions_per_capability,
            tone=tone,
            max_words=max_words_per_capability,
            items_json=json.dumps(items, ensure_ascii=False),
        )
        messages = [
            {"role": "system", "content": BATCH_RECOMMENDATION_SYSTEM_PROMPT + language_directive(language)},
            {"role": "user", "content": user},
        ]
        try:
            content = await self._chat_messages(messages)
        except Exception as exc:
            logger.error("LLM batch recommendation generation failed: %s", exc, exc_info=True)
            return {}

        parsed = self._parse_batch_recommendation_json(content)
        if parsed is None:
            logger.error("LLM batch recommendation response was not valid JSON: %r", content)
            return {}

        return {
            int(item.capability_id): {
                "status": item.status,
                "title": item.title,
                "why_this": item.why_this,
                "evidence_used": item.evidence_used,
                "primary_action": item.primary_action,
                "secondary_action": item.secondary_action,
                "expected_impact": item.expected_impact,
                "clarification_question": item.clarification_question,
            }
            for item in parsed.results
        }

    def _parse_batch_recommendation_json(self, text: str) -> BatchRecommendationResponse | None:
        blob = self._extract_json(text)
        if not isinstance(blob, dict):
            return None
        try:
            return BatchRecommendationResponse.model_validate(blob)
        except ValidationError as exc:
            logger.error("Batch recommendation JSON schema validation failed: %s", exc, exc_info=True)
            return None


def build_recommendation_generator_service(
    settings: Settings,
    chat_messages: Callable[[list[dict[str, str]]], Awaitable[str]],
    clean_text: Callable[[str | None], str],
    extract_json: Callable[[str], dict | None],
) -> RecommendationGeneratorService:
    return RecommendationGeneratorService(
        settings=settings,
        chat_messages=chat_messages,
        clean_text=clean_text,
        extract_json=extract_json,
    )
