"""Cross-provider LLM failover: Mistral -> OpenAI -> Gemini, cycled with a backoff.

Extracted from the desk-research synthesizer so every module that needs a resilient completion
uses the same loop instead of hand-rolling its own. Before this existed, desk research survived a
provider outage while interview-guide generation returned a 500 from the same outage, because it
only knew two providers and one of them was unconfigured.

Credentials are read from the environment only -- a provider with no key is silently skipped
rather than attempted, so an unconfigured failover costs nothing and never appears as a failed
call in the observability table.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Awaitable, Callable, Optional

import httpx

logger = logging.getLogger(__name__)

# (system_prompt, user_prompt) -> completion text, or None when the provider is unconfigured.
ProviderCall = Callable[[str, str], Awaitable[Optional[str]]]

_TIMEOUT = 90.0


async def openai_completion(system_prompt: str, user_prompt: str) -> Optional[str]:
    """OpenAI, or any OpenAI-compatible endpoint. No-op unless OPENAI_API_KEY is set."""
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        return None
    base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("OPENAI_MODEL", "gpt-4.1")
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            res = await client.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
            )
            if res.status_code == 200:
                content = ((res.json().get("choices") or [{}])[0].get("message", {}).get("content") or "").strip()
                if content:
                    logger.info("OpenAI failover succeeded with %s", model)
                    return content
            logger.warning("OpenAI failover returned %d: %s", res.status_code, res.text[:120])
    except Exception as exc:
        logger.warning("OpenAI failover failed: %s", exc)
    return None


async def gemini_completion(system_prompt: str, user_prompt: str) -> Optional[str]:
    """Gemini failover. Tries each configured key against each model in turn.
    No-op unless GEMINI_API_KEYS is set."""
    keys = [k.strip() for k in os.getenv("GEMINI_API_KEYS", "").split(",") if k.strip()]
    if not keys:
        return None
    models = [
        m.strip()
        for m in os.getenv(
            "GEMINI_TEXT_MODELS",
            "gemini-3.5-flash,gemini-3.1-flash-lite,gemini-2.5-flash,gemini-flash-latest",
        ).split(",")
        if m.strip()
    ]
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        for key in keys:
            for model in models:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
                try:
                    res = await client.post(
                        url,
                        json={
                            "systemInstruction": {"parts": [{"text": system_prompt}]},
                            "contents": [{"parts": [{"text": user_prompt}]}],
                        },
                    )
                    if res.status_code == 200:
                        parts = res.json()["candidates"][0]["content"]["parts"]
                        text = "".join(p.get("text", "") for p in parts).strip()
                        if text:
                            logger.info("Gemini failover succeeded with %s", model)
                            return text
                except Exception:
                    continue
    return None


async def complete_with_failover(
    system_prompt: str,
    user_prompt: str,
    *,
    primary: ProviderCall | None = None,
    providers: list[tuple[str, ProviderCall]] | None = None,
    label: str = "llm",
    cycles: int = 2,
) -> str:
    """Run the providers in order, cycling with a backoff between passes.

    Either pass ``providers`` (an explicit ordered list, e.g. OpenAI first for issue generation)
    or ``primary``, which keeps the original Mistral-first order for existing callers.

    The backoff matters for the common case: a rate-limited provider needs time to reset, so
    retrying it immediately just burns another rejection. Returns the first non-empty completion,
    or an ``"Error: ..."`` sentinel the caller can surface to the user.
    """
    if providers is None:
        if primary is None:
            raise ValueError("complete_with_failover needs either `providers` or `primary`")
        providers = [
            ("Mistral", primary),
            ("OpenAI", openai_completion),
            ("Gemini", gemini_completion),
        ]
    last_detail = "no provider was reachable"

    for cycle in range(cycles):
        for name, call in providers:  # type: ignore[union-attr]
            try:
                out = await call(system_prompt, user_prompt)
            except Exception as exc:
                last_detail = f"{name}: {exc}"
                logger.warning("%s: %s failed: %s", label, name, exc)
                continue
            if out and out.strip():
                return out.strip()
            last_detail = f"{name}: empty or unconfigured"
        if cycle < cycles - 1:
            wait = 5 * (cycle + 1)
            logger.warning(
                "%s: all providers failed on pass %d; backing off %ds then retrying from the top",
                label, cycle + 1, wait,
            )
            await asyncio.sleep(wait)

    return f"Error: All LLM providers unavailable (Mistral, OpenAI, Gemini). Last: {last_detail}"
