"""Per-report chat history persistence for the social report assistant.

Mirrors the desk-research chat.json pattern: each report's conversation is stored on disk, keyed
by the report's filename, so it survives a page reload instead of living only in the browser.
Files live in ``scraped_data/chats/`` -- a subdirectory, so ``list_reports`` (which scans the top
level for ``*_report_*.json``) never mistakes a chat log for a report.
"""

from __future__ import annotations

import json
import logging
import os

from app.core.text_normalization import repair_encoding

logger = logging.getLogger(__name__)

_CHATS_DIR = os.path.join("scraped_data", "chats")
_MAX_STORED_MESSAGES = 200


def _chat_path(report_filename: str) -> str:
    """Chat log path for a report, keyed by the report's (already-validated) basename."""
    return os.path.join(_CHATS_DIR, os.path.basename(report_filename))


def load_chat(report_filename: str) -> list[dict]:
    """Load a report's stored chat history (empty if none)."""
    path = _chat_path(report_filename)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        logger.warning("Could not read chat history for %s", report_filename, exc_info=True)
        return []


def append_chat(report_filename: str, messages: list[dict]) -> None:
    """Append turns to a report's chat history (heals mojibake, keeps the last N)."""
    if not messages:
        return
    existing = load_chat(report_filename)
    for m in messages:
        m["text"] = repair_encoding(m.get("text", ""))
        m["sources"] = [repair_encoding(s) for s in (m.get("sources") or [])]
    combined = (existing + messages)[-_MAX_STORED_MESSAGES:]
    try:
        os.makedirs(_CHATS_DIR, exist_ok=True)
        with open(_chat_path(report_filename), "w", encoding="utf-8") as f:
            json.dump(combined, f, ensure_ascii=False, indent=2)
    except Exception:
        logger.warning("Could not persist chat history for %s", report_filename, exc_info=True)


def delete_chat(report_filename: str) -> None:
    """Remove a report's chat history (called when the report itself is deleted)."""
    path = _chat_path(report_filename)
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            logger.warning("Could not delete chat history for %s", report_filename)
