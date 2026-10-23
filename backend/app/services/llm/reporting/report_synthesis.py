"""Writing the report's narrative, from figures that were already computed.

The synthesis is the prose a reader meets first -- what the assessment found, in a few paragraphs.
Every number in it comes from scores calculated in Python and passed in; the model is asked to
explain them, never to work them out. That division is what makes the report reproducible across
runs, and it is the platform's most defensible claim.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import Settings
from app.services.llm.prompts import REPORT_SYNTHESIS_SYSTEM_PROMPT, REPORT_SYNTHESIS_USER_TEMPLATE, language_directive

logger = logging.getLogger(__name__)


class ReportSynthesisResponse(BaseModel):
    executive_summary: str | None = None
    priority_message: str | None = None


class ReportSynthesisService:
    """Executive report synthesis generation."""

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
        self._mistral_rate_limited = False

    def _log_failure(
        self,
        *,
        failure_mode: str,
        company_name: str,
        strongest_axis: str,
        priority_axis: str,
        exc: Exception | None = None,
        raw_content: str | None = None,
    ) -> None:
        extra: dict[str, Any] = {
            "failure_mode": failure_mode,
            "company_name": company_name,
            "strongest_axis": strongest_axis,
            "priority_axis": priority_axis,
        }
        if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
            extra["status_code"] = exc.response.status_code
        if raw_content is not None:
            extra["raw_content_preview"] = raw_content[:500]

        if exc is not None:
            logger.error(
                "LLM report synthesis failed",
                extra=extra,
                exc_info=True,
            )
            return

        logger.error("LLM report synthesis failed", extra=extra)

    def _extract_payload_from_malformed_json(self, content: str) -> dict[str, str] | None:
        normalized = str(content or "").strip()
        if normalized.startswith("```"):
            normalized = re.sub(r"^```(?:json)?\s*", "", normalized, flags=re.IGNORECASE)
            normalized = re.sub(r"\s*```$", "", normalized)

        blob = self._extract_json(normalized)
        if isinstance(blob, dict):
            return blob

        executive_match = re.search(
            r'"executive_summary"\s*:\s*"(?P<value>.*?)"\s*,\s*"priority_message"\s*:',
            normalized,
            flags=re.DOTALL,
        )
        priority_match = re.search(
            r'"priority_message"\s*:\s*"(?P<value>.*?)"\s*\}?\s*$',
            normalized,
            flags=re.DOTALL,
        )
        if executive_match and priority_match:
            return {
                "executive_summary": executive_match.group("value").strip(),
                "priority_message": priority_match.group("value").strip(),
            }

        return None

    async def generate_report_synthesis(
        self,
        company_name: str,
        overall_maturity_band: str,
        overall_score_percent: float,
        strongest_axis: str,
        priority_axis: str,
        strengths_count: int,
        pain_points_count: int,
        axes: list[dict[str, Any]],
        strengths: list[dict[str, Any]],
        pain_points: list[dict[str, Any]],
        language: str = "fr",
    ) -> dict[str, str | None]:
        is_french = (language or "").lower().startswith("fr")
        if is_french:
            axis_strongest_fr = self._fr_axis_label(strongest_axis)
            axis_priority_fr = self._fr_axis_label(priority_axis)
            maturity_band_fr = self._fr_maturity_band_label(overall_maturity_band)
            fallback_summary = (
                f"{company_name} est actuellement au niveau de maturité {maturity_band_fr} "
                f"({round(overall_score_percent)}%). L'axe {axis_strongest_fr} est le plus fort aujourd'hui, "
                f"tandis que l'axe {axis_priority_fr} représente la principale priorité d'amélioration."
            )
            fallback_priority = f"La prochaine étape consiste à renforcer l'exécution dans l'axe {axis_priority_fr} avec un plan d'amélioration ciblé."
        else:
            fallback_summary = (
                f"{company_name} is currently at {overall_maturity_band} maturity "
                f"({round(overall_score_percent)}%). {strongest_axis} is the strongest axis today, "
                f"while {priority_axis} represents the main improvement priority."
            )
            fallback_priority = f"The next step is to strengthen execution in {priority_axis} with a focused improvement plan."


        if not self.settings.mistral_api_key:
            raise RuntimeError("Cannot generate report synthesis because MISTRAL_API_KEY is not set.")
        if self._mistral_rate_limited:
            return {
                "executive_summary": fallback_summary,
                "priority_message": fallback_priority,
            }

        user = REPORT_SYNTHESIS_USER_TEMPLATE.format(
            company_name=company_name,
            overall_maturity_band=overall_maturity_band,
            overall_score_percent=round(overall_score_percent, 2),
            strongest_axis=strongest_axis,
            priority_axis=priority_axis,
            strengths_count=strengths_count,
            pain_points_count=pain_points_count,
            axes_lines=self._format_report_items(axes[:6]),
            strengths_lines=self._format_report_theme_lines(strengths[:3]),
            pain_points_lines=self._format_report_theme_lines(pain_points[:3]),
        )
        try:
            content = await self._chat_messages(
                [
                    {"role": "system", "content": REPORT_SYNTHESIS_SYSTEM_PROMPT + language_directive(language)},
                    {"role": "user", "content": user},
                ]
            )
        except (httpx.ReadTimeout, httpx.ConnectTimeout) as exc:
            self._log_failure(
                failure_mode="timeout",
                company_name=company_name,
                strongest_axis=strongest_axis,
                priority_axis=priority_axis,
                exc=exc,
            )
            raise
        except httpx.HTTPStatusError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                self._mistral_rate_limited = True
                logger.warning(
                    "Mistral rate limit reached during report synthesis; using fallback copy.",
                    extra={
                        "failure_mode": "429",
                        "company_name": company_name,
                        "strongest_axis": strongest_axis,
                        "priority_axis": priority_axis,
                        "status_code": 429,
                    },
                )
                return {
                    "executive_summary": fallback_summary,
                    "priority_message": fallback_priority,
                }
            self._log_failure(
                failure_mode="http_status",
                company_name=company_name,
                strongest_axis=strongest_axis,
                priority_axis=priority_axis,
                exc=exc,
            )
            raise
        except Exception as exc:
            self._log_failure(
                failure_mode="unexpected_exception",
                company_name=company_name,
                strongest_axis=strongest_axis,
                priority_axis=priority_axis,
                exc=exc,
            )
            raise

        blob = self._extract_payload_from_malformed_json(content)
        if not isinstance(blob, dict):
            self._log_failure(
                failure_mode="invalid_json",
                company_name=company_name,
                strongest_axis=strongest_axis,
                priority_axis=priority_axis,
                raw_content=content,
            )
            raise ValueError("LLM report synthesis returned invalid JSON.")
        if not self._extract_json(content):
            logger.warning(
                "Recovered malformed report synthesis payload without degrading the report.",
                extra={
                    "company_name": company_name,
                    "strongest_axis": strongest_axis,
                    "priority_axis": priority_axis,
                    "recovery_mode": "multiline_json_strings",
                },
            )
        try:
            parsed = ReportSynthesisResponse.model_validate(blob)
        except ValidationError as exc:
            self._log_failure(
                failure_mode="schema_validation",
                company_name=company_name,
                strongest_axis=strongest_axis,
                priority_axis=priority_axis,
                exc=exc,
                raw_content=content,
            )
            raise

        return {
            "executive_summary": self._clean_text(parsed.executive_summary or "") or fallback_summary,
            "priority_message": self._clean_text(parsed.priority_message or "") or fallback_priority,
        }

    def _format_report_items(self, items: list[dict[str, Any]]) -> str:
        lines = [
            f"- {item.get('axis')}: {item.get('score_percent')}% ({item.get('maturity_band')})"
            for item in items
        ]
        return "\n".join(lines) or "- none"

    def _format_report_theme_lines(self, items: list[dict[str, Any]]) -> str:
        lines = [
            "- "
            f"{item.get('capability')} [{item.get('axis')}] "
            f"confidence={item.get('confidence_label') or 'unknown'} "
            f"evidence={item.get('evidence_strength') or 'unknown'}: "
            f"{item.get('rationale') or 'No rationale provided'}"
            for item in items
        ]
        return "\n".join(lines) or "- none"

    def _fr_axis_label(self, axis: str) -> str:
        key = str(axis).lower().strip()
        mapping = {
            "manage": "Gérer",
            "analyze": "Analyser",
            "improve": "Améliorer",
        }
        return mapping.get(key, axis)

    def _fr_maturity_band_label(self, band: str) -> str:
        key = str(band).lower().strip()
        mapping = {
            "basic": "Basique",
            "established": "Établi",
            "advanced": "Avancé",
            "in progress": "En cours",
            "not scored": "Non évalué",
        }
        return mapping.get(key, band)



def build_report_synthesis_service(
    settings: Settings,
    chat_messages: Callable[[list[dict[str, str]]], Awaitable[str]],
    clean_text: Callable[[str | None], str],
    extract_json: Callable[[str], dict | None],
) -> ReportSynthesisService:
    return ReportSynthesisService(
        settings=settings,
        chat_messages=chat_messages,
        clean_text=clean_text,
        extract_json=extract_json,
    )
