"""Per-guide chat history persistence for the interview assistant.

Keyed by the saved guide's integer id (the guide itself lives in the database; only the
conversation is stored here, as JSON, so it survives a reload). Same shape as the desk-research
and social report chat stores.
"""

from __future__ import annotations

import json
import logging
import os

from app.core.text_normalization import repair_encoding

logger = logging.getLogger(__name__)

_DIR = "interview_chat_data"
_MAX_STORED_MESSAGES = 200


def _path(guide_id: int) -> str:
    # int() coercion also sanitizes the id against any path shenanigans.
    return os.path.join(_DIR, f"{int(guide_id)}.json")


def load_chat(guide_id: int) -> list[dict]:
    try:
        path = _path(guide_id)
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        logger.warning("Could not read interview chat for guide %s", guide_id, exc_info=True)
        return []


def append_chat(guide_id: int, messages: list[dict]) -> None:
    if not messages:
        return
    existing = load_chat(guide_id)
    for m in messages:
        m["text"] = repair_encoding(m.get("text", ""))
        m["sources"] = [repair_encoding(s) for s in (m.get("sources") or [])]
    combined = (existing + messages)[-_MAX_STORED_MESSAGES:]
    try:
        os.makedirs(_DIR, exist_ok=True)
        with open(_path(guide_id), "w", encoding="utf-8") as f:
            json.dump(combined, f, ensure_ascii=False, indent=2)
    except Exception:
        logger.warning("Could not persist interview chat for guide %s", guide_id, exc_info=True)


def delete_chat(guide_id: int) -> None:
    path = _path(guide_id)
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            logger.warning("Could not delete interview chat for guide %s", guide_id)
