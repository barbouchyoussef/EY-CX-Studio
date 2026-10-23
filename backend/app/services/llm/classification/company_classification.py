"""Guessing a company's sector and size from its name alone.

The first question the diagnostic asks is the company name, and answering the next two from it --
sector and size -- saves the client two questions before anything interesting has been asked.

A guess, so it is guarded: anything the model returns is checked against the reference tables, and
an unrecognised value falls back to asking. Being wrong about a client's own sector in the opening
exchange costs more than the two questions it saved.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from app.core.config import Settings
from app.services.llm.prompts import COMPANY_CLASSIFICATION_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class CompanyClassificationService:
    """Company sector/size classification with guarded fallback."""

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

    async def classify_company(self, company_name: str, sector_options: list[dict], size_options: list[dict]) -> dict:
        if not self.settings.mistral_api_key:
            logger.error("Cannot classify company because MISTRAL_API_KEY is not set.")
            return self._fallback_company_classification(sector_options, size_options)

        messages = self._build_company_classification_messages(company_name, sector_options, size_options)
        try:
            content = await self._chat_messages(messages)
        except Exception as exc:
            logger.error("LLM company classification failed: %s", exc, exc_info=True)
            return self._fallback_company_classification(sector_options, size_options)

        data = self._extract_json(content) or {}
        sector_code = str(data.get("sector_code") or "").strip().lower()
        size_code = str(data.get("company_size_code") or "").strip().lower()
        allowed_sectors = {str(o.get("code", "")).strip().lower() for o in sector_options}
        allowed_sizes = {str(o.get("code", "")).strip().lower() for o in size_options}

        if sector_code not in allowed_sectors:
            logger.error("Invalid sector_code returned by LLM: %r", sector_code)
            return self._fallback_company_classification(sector_options, size_options)
        if size_code not in allowed_sizes:
            logger.error("Invalid company_size_code returned by LLM: %r", size_code)
            return self._fallback_company_classification(sector_options, size_options)
        return {"sector_code": sector_code, "company_size_code": size_code}

    def _build_company_classification_messages(
        self,
        company_name: str,
        sector_options: list[dict],
        size_options: list[dict],
    ) -> list[dict[str, str]]:
        sectors_text = "\n".join(f"- code={o['code']} label={o['label']}" for o in sector_options[:200])
        sizes_text = "\n".join(f"- code={o['code']} label={o['label']}" for o in size_options[:200])
        user = (
            f"Company name: {company_name}\n\n"
            "Sector options:\n"
            f"{sectors_text}\n\n"
            "Company size options:\n"
            f"{sizes_text}\n\n"
            "Return JSON:\n"
            '{ "sector_code": "retail", "company_size_code": "small" }'
        )
        return [{"role": "system", "content": COMPANY_CLASSIFICATION_SYSTEM_PROMPT}, {"role": "user", "content": user}]

    def _fallback_company_classification(self, sector_options: list[dict], size_options: list[dict]) -> dict:
        return {
            "sector_code": self._fallback_option_code(sector_options),
            "company_size_code": self._fallback_option_code(size_options),
        }

    def _fallback_option_code(self, options: list[dict]) -> str:
        if not options:
            raise ValueError("Cannot fallback company classification because reference options are empty.")
        normalized_options = [
            (str(option.get("code", "")).strip().lower(), option)
            for option in options
            if str(option.get("code", "")).strip()
        ]
        if not normalized_options:
            raise ValueError("Cannot fallback company classification because reference option codes are empty.")
        for preferred in ("other", "unknown", "general"):
            for code, _option in normalized_options:
                if code == preferred:
                    return code
        return normalized_options[0][0]


def build_company_classification_service(
    settings: Settings,
    chat_messages: Callable[[list[dict[str, str]]], Awaitable[str]],
    clean_text: Callable[[str | None], str],
    extract_json: Callable[[str], dict | None],
) -> CompanyClassificationService:
    return CompanyClassificationService(
        settings=settings,
        chat_messages=chat_messages,
        clean_text=clean_text,
        extract_json=extract_json,
    )
