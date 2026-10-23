"""Robust Multi-Provider VLM client supporting Gemini Flash Lite series and OpenRouter failover."""

import os
import re
import base64
import logging
import time
import asyncio
from typing import Optional, List, Dict
import httpx
from PIL import Image
import io

logger = logging.getLogger(__name__)


class MultiProviderVLMClient:
    """Multi-tier VLM client: Gemini key/model rotation -> OpenRouter failover -> Local OCR."""

    def __init__(self):
        try:
            from app.core.config import load_env_file
            load_env_file()
        except Exception:
            pass

        # 1. Gemini Config
        raw_gemini_keys = os.getenv("GEMINI_API_KEYS", "")
        self.gemini_keys = [k.strip().strip('"\'') for k in raw_gemini_keys.split(",") if k.strip()]
        
        # Newest-first vision models (verified against the live ListModels API, Jul 2026).
        # 'gemini-flash-lite-latest' is an auto-tracking alias so this keeps working as the
        # line advances. Override via env (GEMINI_VLM_MODELS) at any time.
        raw_gemini_models = os.getenv(
            "GEMINI_VLM_MODELS",
            "gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemini-2.5-flash-lite,gemini-flash-lite-latest"
        )
        self.gemini_models = [m.strip() for m in raw_gemini_models.split(",") if m.strip()]
        
        self.current_key_idx = 0
        self.key_cooldowns: Dict[str, float] = {}  # key -> timestamp when available again

        # 2. OpenRouter Config
        raw_or_key = os.getenv("OPENROUTER_API_KEY", "")
        self.openrouter_key = raw_or_key.strip().strip('"\'') if raw_or_key else None
        self.openrouter_model = os.getenv("OPENROUTER_VLM_MODEL", "nvidia/nemotron-nano-12b-v2-vl:free")

    def _get_next_available_gemini_key(self) -> Optional[str]:
        """Return next non-cooldowned Gemini key."""
        if not self.gemini_keys:
            return None

        now = time.time()
        n_keys = len(self.gemini_keys)

        for _ in range(n_keys):
            key = self.gemini_keys[self.current_key_idx]
            cooldown_until = self.key_cooldowns.get(key, 0)
            if now >= cooldown_until:
                return key
            self.current_key_idx = (self.current_key_idx + 1) % n_keys

        return None

    def _mark_key_cooldown(self, key: str, retry_after_sec: float = 10.0) -> None:
        """Mark a key as cooling down and rotate to next key."""
        self.key_cooldowns[key] = time.time() + retry_after_sec
        if self.gemini_keys:
            self.current_key_idx = (self.current_key_idx + 1) % len(self.gemini_keys)

    def describe_image(self, pil_image: Image.Image, prompt: str = "") -> Optional[str]:
        """Synchronous VLM description with Gemini rotation and OpenRouter failover."""
        prompt = prompt or _DEFAULT_VLM_PROMPT

        import time
        from app.services.observability.llm_metrics import mark_llm, log_llm_call

        _start = time.monotonic()
        mark_llm(feature="desk.vlm", kind="run")

        # Convert PIL image to Base64
        img_buffer = io.BytesIO()
        pil_image.save(img_buffer, format="PNG")
        img_b64 = base64.b64encode(img_buffer.getvalue()).decode("utf-8")

        with httpx.Client(timeout=30.0) as client:
            # 1. Try Gemini
            if self.gemini_keys:
                payload = {
                    "contents": [
                        {
                            "parts": [
                                {"text": prompt},
                                {
                                    "inline_data": {
                                        "mime_type": "image/png",
                                        "data": img_b64,
                                    }
                                },
                            ]
                        }
                    ]
                }
                for model in self.gemini_models:
                    key = self._get_next_available_gemini_key()
                    if not key:
                        break
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
                    try:
                        res = client.post(url, json=payload)
                        if res.status_code == 429:
                            self._mark_key_cooldown(key, 15.0)
                            continue
                        if res.status_code != 200:
                            continue
                        data = res.json()
                        text = _gemini_text(data)
                        if not text:
                            continue
                        logger.info("Gemini VLM model %s succeeded via key %s...", model, key[:8])
                        _um = data.get("usageMetadata", {}) or {}
                        log_llm_call(
                            provider="gemini", model=model, ok=True,
                            latency_ms=int((time.monotonic() - _start) * 1000),
                            usage={"prompt_tokens": _um.get("promptTokenCount"),
                                   "completion_tokens": _um.get("candidatesTokenCount"),
                                   "total_tokens": _um.get("totalTokenCount")},
                            input_messages=[{"role": "user", "content": prompt}],
                            output_text=text,
                        )
                        return text
                    except Exception as e:
                        logger.warning("Gemini VLM sync request failed: %s", e)

            # 2. Try OpenRouter Failover
            if self.openrouter_key:
                logger.info("Failing over to OpenRouter VLM...")
                headers = {
                    "Authorization": f"Bearer {self.openrouter_key}",
                    "HTTP-Referer": "http://localhost:8000",
                    "X-Title": "CX Chat Desk Research",
                }
                for model in [self.openrouter_model, "openrouter/free"]:
                    payload = {
                        "model": model,
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    {
                                        "type": "image_url",
                                        "image_url": {"url": f"data:image/png;base64,{img_b64}"}
                                    }
                                ]
                            }
                        ]
                    }
                    try:
                        res = client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
                        if res.status_code != 200:
                            continue
                        data = res.json()
                        content = _openrouter_text(data)
                        if not content:
                            continue
                        logger.info("OpenRouter VLM model %s succeeded!", model)
                        log_llm_call(
                            provider="openrouter", model=model, ok=True,
                            latency_ms=int((time.monotonic() - _start) * 1000),
                            usage=data.get("usage"),
                            input_messages=[{"role": "user", "content": prompt}],
                            output_text=content,
                        )
                        return content

                    except Exception as e:
                        logger.warning("OpenRouter VLM sync request failed for %s: %s", model, e)

        logger.warning("All VLM providers exhausted in sync call.")
        return None

    async def describe_image_async(self, pil_image: Image.Image, prompt: str = "") -> Optional[str]:
        """Asynchronous wrapper."""
        return await asyncio.to_thread(self.describe_image, pil_image, prompt)


# The instruction sent with every image. Kept at module level so a wording change is a visible
# one-line diff rather than an edit buried in the middle of a request function.
_DEFAULT_VLM_PROMPT = (
    "You are extracting content from a business/analytics document for a report. "
    "If this image is a chart, graph, table, or infographic, transcribe its data "
    "precisely: the title, axis/category labels, every series, and every "
    "number, percentage and date shown -- as a compact markdown table or list. "
    "If it contains readable Arabic or English text, transcribe it accurately. "
    "ONLY if the image is unmistakably decorative -- a logo, brand wordmark, banner, "
    "header, footer, icon, divider, or solid background with NO chart, table, or data "
    "-- reply with EXACTLY the single word: DECORATIVE (nothing else). If it shows any "
    "chart, table, numbers, or substantive text, describe it as above; when in doubt, "
    "describe it."
)


def _gemini_text(payload: dict) -> Optional[str]:
    """The description out of a Gemini response, or None if the response is not that shape.

    Every level here used to be an `if` nested inside the request loop. A provider can return 200
    with a body that carries no text at all -- a safety block, or an empty candidate list -- so
    each step is checked; the difference is that failing now means "None", not another indent.
    """
    candidates = payload.get("candidates") or []
    if not candidates:
        return None
    parts = (candidates[0].get("content") or {}).get("parts") or []
    if not parts:
        return None
    return (parts[0].get("text") or "").strip() or None


def _openrouter_text(payload: dict) -> Optional[str]:
    """The description out of an OpenRouter (OpenAI-shaped) response, or None."""
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    return ((choices[0].get("message") or {}).get("content") or "").strip() or None


# Global singleton instance
_vlm_instance: Optional[MultiProviderVLMClient] = None


def get_vlm_client() -> MultiProviderVLMClient:
    """Return cached MultiProviderVLMClient instance."""
    global _vlm_instance
    if _vlm_instance is None:
        _vlm_instance = MultiProviderVLMClient()
    return _vlm_instance
