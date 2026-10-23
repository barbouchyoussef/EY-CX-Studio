"""Session store for desk research.

Durable data — session metadata, chat, processed documents, and uploaded originals — lives in
object storage via ``app.services.storage``, so it survives restarts on an ephemeral host. Which
backend (local disk vs Supabase) is chosen by ``STORAGE_BACKEND``; this module only ever deals in
string *keys*, never real paths, for that data.

Extracted figure images are deliberately NOT stored here: the VLM captions each image in memory
during extraction and writes the *text* into the processed document, and the PNGs are never read
again. They stay in a local scratch dir (written during extraction) and are disposable.

Storage keys (all under one prefix, so deleting the prefix removes a whole session):
    desk_research_data/<sid>/session.json          -- metadata sidecar
    desk_research_data/<sid>/chat.json             -- persisted chat
    desk_research_data/<sid>/processed/<doc>.json  -- one per processed document
    desk_research_data/<sid>/originals/<safe_name> -- uploaded files (kept for re-processing)
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import unicodedata
from datetime import datetime, timezone
from hashlib import sha1
from pathlib import Path
from uuid import uuid4

from app.core.text_normalization import repair_encoding
from app.schemas.desk_research import (
    DocumentSummary,
    ProcessedDocument,
    SessionInfo,
    StoredChatMessage,
)
from app.services import storage

logger = logging.getLogger(__name__)

_ROOT = "desk_research_data"                    # storage key prefix (durable data)
_IMAGES_SCRATCH = Path("desk_research_data")    # LOCAL scratch for throwaway extraction images

MAX_FILES_PER_SESSION = 10
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
_MAX_STORED_MESSAGES = 200


# ---------------------------------------------------------------------------
# Key helpers (strings — there are no folders in object storage)
# ---------------------------------------------------------------------------

def _segment(value: str) -> str:
    """One path segment of a storage key, with traversal refused.

    Session and document ids arrive from the URL and are interpolated into a key that the disk
    backend resolves with ``root / key`` -- which happily walks out of the root when given
    ``../``. Nothing today gets that far, because every route resolves its session through
    ``_session_or_404`` first and a traversal id matches no session. That is a guard doing this
    job by accident, and it stops working the moment someone writes a route that reads before it
    resolves. Refusing the characters here means the key can never leave the prefix, whichever
    caller builds it.

    Deliberately not a format check: ids are ``uuid4().hex[:16]`` today, but sessions created by
    fixtures and benchmarks are named things like ``audit_sess``, and rejecting them would break
    reading data that already exists.
    """
    if not value or value in (".", "..") or any(c in value for c in ("/", chr(92), chr(0))):
        raise ValueError(f"unsafe storage key segment: {value!r}")
    return value


def _session_prefix(session_id: str) -> str:
    return f"{_ROOT}/{_segment(session_id)}"

def _meta_key(session_id: str) -> str:
    return f"{_ROOT}/{_segment(session_id)}/session.json"

def _chat_key(session_id: str) -> str:
    return f"{_ROOT}/{_segment(session_id)}/chat.json"

def _processed_prefix(session_id: str) -> str:
    return f"{_ROOT}/{_segment(session_id)}/processed"

def _processed_key(session_id: str, doc_id: str) -> str:
    return f"{_ROOT}/{_segment(session_id)}/processed/{_segment(doc_id)}.json"

def _originals_prefix(session_id: str) -> str:
    return f"{_ROOT}/{_segment(session_id)}/originals"

def _original_key(session_id: str, safe_name: str) -> str:
    return f"{_ROOT}/{_segment(session_id)}/originals/{_segment(safe_name)}"


def _images_dir(session_id: str, doc_id: str) -> Path:
    """LOCAL scratch dir for extracted figure images — throwaway, never uploaded."""
    return _IMAGES_SCRATCH / session_id / "images" / doc_id


def _safe_object_name(filename: str) -> str:
    """An ASCII-safe storage key segment for an uploaded file. Object stores (Supabase) reject
    non-ASCII keys, so we slug the name to ASCII and append a short hash of the ORIGINAL name to
    stay unique and deterministic even when the name is fully non-Latin (e.g. Arabic). The real
    display name is preserved separately on the ProcessedDocument."""
    name = Path(filename).name
    stem = unicodedata.normalize("NFKD", Path(name).stem).encode("ascii", "ignore").decode("ascii")
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-") or "file"
    ext = re.sub(r"[^A-Za-z0-9.]", "", Path(name).suffix.lower())
    return f"{stem}_{sha1(name.encode('utf-8')).hexdigest()[:8]}{ext}"


# ---------------------------------------------------------------------------
# Chat history
# ---------------------------------------------------------------------------

def load_chat(session_id: str) -> list[StoredChatMessage]:
    key = _chat_key(session_id)
    if not storage.exists(key):
        return []
    try:
        return [StoredChatMessage(**m) for m in json.loads(storage.get_text(key))]
    except Exception:
        logger.warning("Could not read chat history for %s", session_id, exc_info=True)
        return []


def append_chat(session_id: str, messages: list[StoredChatMessage]) -> None:
    if not messages:
        return
    existing = load_chat(session_id)
    for m in messages:
        m.text = repair_encoding(m.text)
        m.sources = [repair_encoding(s) for s in m.sources]
    combined = (existing + messages)[-_MAX_STORED_MESSAGES:]
    storage.put_text(
        _chat_key(session_id),
        json.dumps([m.model_dump() for m in combined], ensure_ascii=False, indent=2),
    )


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

def create_session(title: str | None = None, owner_id: int | None = None) -> SessionInfo:
    session_id = uuid4().hex[:16]
    now = datetime.now(timezone.utc).isoformat()
    info = SessionInfo(session_id=session_id, created_at=now, title=title, owner_id=owner_id)
    _write_meta(session_id, info)  # no folders to create in object storage
    logger.info("Created desk-research session %s", session_id)
    return info


def rename_session(session_id: str, title: str) -> bool:
    if not storage.exists(_meta_key(session_id)):
        return False
    info = _read_meta(session_id)
    info.title = (title or "").strip() or None
    _write_meta(session_id, info)
    logger.info("Renamed session %s to %r", session_id, info.title)
    return True


def save_report(session_id: str, markdown: str, user_context: str | None = None,
                title: str | None = None, cx_findings: list[dict] | None = None,
                document_analyses: list[str] | None = None,
                report_overview: dict | None = None) -> None:
    """Persist a generated report onto the session so it survives reloads.

    ``cx_findings`` is the structured CX-capability mapping -- persisted (not just embedded in the
    markdown) so the consolidated issue log can consume it directly, without re-running the LLM."""
    if not storage.exists(_meta_key(session_id)):
        return
    info = _read_meta(session_id)
    info.report_markdown = markdown
    info.report_generated_at = datetime.now(timezone.utc).isoformat()
    info.has_report = True
    if document_analyses is not None:
        info.document_analyses = document_analyses
    if cx_findings is not None:
        info.cx_findings = cx_findings
    if report_overview is not None:
        info.report_overview = report_overview
    if user_context is not None:
        info.user_context = user_context
    if title:
        info.title = title
    _write_meta(session_id, info)
    logger.info("Saved report onto session %s", session_id)


def get_session(session_id: str) -> SessionInfo | None:
    """Load session metadata and document summaries, or ``None``.

    An id that cannot form a safe key is simply "not found": every route resolves a session
    through here first, so this is what turns a hostile id into a 404 rather than a 500.
    """
    try:
        meta_key = _meta_key(session_id)
    except ValueError:
        logger.warning("Rejected unsafe desk research session id: %r", session_id)
        return None
    if not storage.exists(meta_key):
        return None
    info = _read_meta(session_id)

    docs: list[DocumentSummary] = []
    for key in storage.list_keys(_processed_prefix(session_id)):
        if not key.endswith(".json"):
            continue
        try:
            doc = ProcessedDocument.model_validate_json(storage.get_text(key))
            docs.append(DocumentSummary(
                doc_id=doc.doc_id,
                filename=repair_encoding(doc.filename),  # heal mojibake filenames
                format=doc.format,
                status=doc.status,
                page_count=doc.page_count,
                block_count=len(doc.blocks),
            ))
        except Exception:
            logger.warning("Could not read processed doc %s", key)

    info.documents = docs
    info.document_count = len(docs)
    info.report_markdown = repair_encoding(info.report_markdown) if info.report_markdown else info.report_markdown
    info.title = repair_encoding(info.title) if info.title else info.title
    info.has_report = bool(info.report_markdown)
    info.messages = load_chat(session_id)
    return info


def delete_session(session_id: str) -> bool:
    if not storage.exists(_meta_key(session_id)):
        return False
    storage.delete_prefix(_session_prefix(session_id))
    local = _IMAGES_SCRATCH / session_id  # throwaway local images
    if local.exists():
        shutil.rmtree(local, ignore_errors=True)
    logger.info("Deleted desk-research session %s", session_id)
    return True


def list_sessions() -> list[SessionInfo]:
    """List all existing sessions (lightweight — no document details)."""
    keys = storage.list_keys(_ROOT)
    session_ids = {
        parts[1] for k in keys
        if k.endswith("/session.json") and len(parts := k.split("/")) == 3
    }
    sessions: list[SessionInfo] = []
    for sid in session_ids:
        try:
            info = _read_meta(sid)
        except Exception:
            logger.warning("Could not read meta for session %s", sid)
            continue
        info.document_count = sum(
            1 for k in keys if k.startswith(_processed_prefix(sid) + "/") and k.endswith(".json")
        )
        info.has_report = bool(info.report_markdown)
        info.report_markdown = None  # keep the list lightweight
        info.documents = []
        sessions.append(info)
    sessions.sort(key=lambda s: s.created_at, reverse=True)  # newest first
    return sessions


# ---------------------------------------------------------------------------
# File storage
# ---------------------------------------------------------------------------

def save_original(session_id: str, filename: str, content: bytes) -> str:
    """Save an uploaded file to durable storage under an ASCII-safe key. Returns the storage key.

    Raises ValueError if the session is at its file limit or the file is too large."""
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise ValueError(
            f"File '{filename}' is {len(content) / 1024 / 1024:.1f} MB — "
            f"max allowed is {MAX_FILE_SIZE_BYTES / 1024 / 1024:.0f} MB."
        )
    existing = storage.list_keys(_originals_prefix(session_id))
    key = _original_key(session_id, _safe_object_name(filename))
    if key not in existing and len(existing) >= MAX_FILES_PER_SESSION:
        raise ValueError(f"Session already has {len(existing)} files — max is {MAX_FILES_PER_SESSION}.")
    storage.put_bytes(key, content)
    logger.info("Saved original %s -> %s", filename, key)
    return key


def save_processed(session_id: str, doc: ProcessedDocument) -> str:
    """Persist a ``ProcessedDocument`` as JSON. Returns its storage key."""
    key = _processed_key(session_id, doc.doc_id)
    storage.put_text(key, doc.model_dump_json(indent=2))
    logger.info("Saved processed doc %s -> %s", doc.doc_id, key)
    return key


def delete_document(session_id: str, doc_id: str) -> bool:
    """Remove one processed document (its JSON + any local throwaway images). True if it existed."""
    key = _processed_key(session_id, doc_id)
    existed = storage.exists(key)
    if existed:
        storage.delete(key)
    local_images = _images_dir(session_id, doc_id)
    if local_images.exists():
        shutil.rmtree(local_images, ignore_errors=True)
    return existed


def load_processed(session_id: str, doc_id: str) -> ProcessedDocument | None:
    key = _processed_key(session_id, doc_id)
    if not storage.exists(key):
        return None
    try:
        return ProcessedDocument.model_validate_json(storage.get_text(key))
    except Exception:
        logger.warning("Could not parse processed doc %s", key)
        return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _write_meta(session_id: str, info: SessionInfo) -> None:
    storage.put_text(_meta_key(session_id), info.model_dump_json(indent=2))


def _read_meta(session_id: str) -> SessionInfo:
    return SessionInfo.model_validate_json(storage.get_text(_meta_key(session_id)))
