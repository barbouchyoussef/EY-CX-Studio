"""Instrumented chat completions: one model per call, status and usage always returned.

``failover.py`` answers "give me some text from whichever provider works" and returns a bare
string. That is right for a single user-facing completion, but a pipeline that fans out dozens of
calls needs to know WHY something failed -- a 429 means wait, a 401 means stop -- and how many
tokens it cost. This module returns that; ``throttle.guarded`` consumes it.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 300.0


@dataclass
class Completion:
    ok: bool
    text: str = ""
    error: str = ""
    status: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    seconds: float = 0.0
    provider: str = ""
    model: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


def _timeout() -> float:
    try:
        return float(os.getenv("LLM_TIMEOUT_SECONDS", "").strip() or DEFAULT_TIMEOUT)
    except ValueError:
        return DEFAULT_TIMEOUT


def _key(name: str) -> str:
    # --env-file does not strip quotes; a quoted key produced `Bearer "sk-..."` and a 401 on
    # every call, which looked like an application bug for a full day.
    return os.getenv(name, "").strip().strip('"').strip("'")


async def openai_chat(model: str, system: str, user: str) -> Completion:
    key = _key("OPENAI_API_KEY")
    if not key:
        return Completion(False, error="OPENAI_API_KEY not set", provider="openai", model=model)
    base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=_timeout()) as client:
            res = await client.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": model, "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user}]},
            )
    except Exception as exc:
        return Completion(False, error=f"{type(exc).__name__}: {exc}", provider="openai",
                          model=model, seconds=time.monotonic() - started)

    elapsed = time.monotonic() - started
    if res.status_code == 200:
        data = res.json()
        text = ((data.get("choices") or [{}])[0].get("message", {}).get("content") or "").strip()
        usage = data.get("usage") or {}
        return Completion(bool(text), text, "" if text else "empty content", 200,
                          usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0),
                          elapsed, "openai", model)
    return Completion(False, error=f"HTTP {res.status_code}: {res.text[:300]}",
                      status=res.status_code, seconds=elapsed, provider="openai", model=model)


async def mistral_chat(model: str, system: str, user: str) -> Completion:
    key = _key("MISTRAL_API_KEY")
    if not key:
        return Completion(False, error="MISTRAL_API_KEY not set", provider="mistral", model=model)
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=_timeout()) as client:
            res = await client.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": model, "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user}]},
            )
    except Exception as exc:
        return Completion(False, error=f"{type(exc).__name__}: {exc}", provider="mistral",
                          model=model, seconds=time.monotonic() - started)

    elapsed = time.monotonic() - started
    if res.status_code == 200:
        data = res.json()
        text = ((data.get("choices") or [{}])[0].get("message", {}).get("content") or "").strip()
        usage = data.get("usage") or {}
        return Completion(bool(text), text, "" if text else "empty content", 200,
                          usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0),
                          elapsed, "mistral", model)
    return Completion(False, error=f"HTTP {res.status_code}: {res.text[:300]}",
                      status=res.status_code, seconds=elapsed, provider="mistral", model=model)


async def gemini_chat(model: str, system: str, user: str) -> Completion:
    keys = [k.strip() for k in os.getenv("GEMINI_API_KEYS", "").split(",") if k.strip()]
    if not keys:
        return Completion(False, error="GEMINI_API_KEYS not set", provider="gemini", model=model)
    started = time.monotonic()
    last = "no key worked"
    for key in keys:
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{model}:generateContent?key={key}")
        try:
            async with httpx.AsyncClient(timeout=_timeout()) as client:
                res = await client.post(url, json={
                    "systemInstruction": {"parts": [{"text": system}]},
                    "contents": [{"parts": [{"text": user}]}]})
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"
            continue
        if res.status_code == 200:
            data = res.json()
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts).strip()
            usage = data.get("usageMetadata") or {}
            return Completion(bool(text), text, "" if text else "empty content", 200,
                              usage.get("promptTokenCount", 0),
                              usage.get("candidatesTokenCount", 0),
                              time.monotonic() - started, "gemini", model)
        last = f"HTTP {res.status_code}: {res.text[:200]}"
        if res.status_code not in (429, 403):        # try the next key only on quota/auth errors
            break
    return Completion(False, error=last, seconds=time.monotonic() - started,
                      provider="gemini", model=model)


CHAT = {"openai": openai_chat, "mistral": mistral_chat, "gemini": gemini_chat}


async def chat(provider: str, model: str, system: str, user: str) -> Completion:
    fn = CHAT.get(provider)
    if fn is None:
        return Completion(False, error=f"unknown provider {provider!r}",
                          provider=provider, model=model)
    return await fn(model, system, user)


def configured_providers() -> list[str]:
    """Which providers have credentials. An unconfigured provider is skipped rather than tried,
    so it never appears as a failed call in the observability table."""
    out = []
    if _key("OPENAI_API_KEY"):
        out.append("openai")
    if _key("MISTRAL_API_KEY"):
        out.append("mistral")
    if os.getenv("GEMINI_API_KEYS", "").strip():
        out.append("gemini")
    return out
