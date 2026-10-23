"""FastAPI routes for the Desk Research document processing module."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.dependencies.auth import get_current_user
from app.dependencies.db import get_db
from app.services.auth import access
from pydantic import BaseModel, Field

from app.schemas.desk_research import (
    DocumentSummary,
    ProcessedDocument,
    SessionInfo,
    UploadResponse,
)
from app.services.desk_research import converter, pipeline, session_manager


async def _session_or_404(
    session_id: str, user: User, db: AsyncSession, *, owner_only: bool = False
) -> SessionInfo:
    """Load a session and enforce access. 404 (not 403) so existence isn't confirmed."""
    info = session_manager.get_session(session_id)
    if not info:
        raise HTTPException(404, detail="Session not found")
    is_owner = info.owner_id == user.id
    if owner_only:
        if not is_owner:
            raise HTTPException(404, detail="Session not found")
    elif not is_owner and not await access.can_view_via_project_or_share(
        db, user.id, "desk_session", session_id
    ):
        raise HTTPException(404, detail="Session not found")
    return info

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/desk-research", tags=["desk-research"], dependencies=[Depends(get_current_user)]
)


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


@router.post("/sessions", response_model=SessionInfo, status_code=201)
async def create_session(user: User = Depends(get_current_user)):
    """Create a new desk-research session, owned by the caller."""
    return session_manager.create_session(owner_id=user.id)


@router.get("/sessions", response_model=list[SessionInfo])
async def list_sessions(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """List sessions the user may see (owned, shared, or attached to their projects)."""
    visible = await access.visible_refs(db, user.id, "desk_session")
    out = []
    for s in session_manager.list_sessions():
        if s.owner_id == user.id or s.session_id in visible:
            s.owned = s.owner_id == user.id
            out.append(s)
    return out


@router.get("/sessions/{session_id}", response_model=SessionInfo)
async def get_session(
    session_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Get session info including its document list."""
    await _session_or_404(session_id, user, db)
    return session_manager.get_session(session_id)


class RenameRequest(BaseModel):
    title: str = Field(..., description="New display title for the session")


@router.patch("/sessions/{session_id}", response_model=SessionInfo)
async def rename_session(
    session_id: str,
    body: RenameRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Rename a session. Returns the updated session info."""
    await _session_or_404(session_id, user, db)
    if not session_manager.rename_session(session_id, body.title):
        raise HTTPException(404, detail="Session not found")
    return session_manager.get_session(session_id)


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Delete a session and all its files (owner only)."""
    await _session_or_404(session_id, user, db, owner_only=True)
    if not session_manager.delete_session(session_id):
        raise HTTPException(404, detail="Session not found")
    from app.services.desk_research import rag_index
    from app.services.projects import project_service as project_svc

    rag_index.delete_index(session_id)
    # Clear any project links / shares that pointed at this session.
    await project_svc.cleanup_analysis_links(db, "desk_session", session_id)


# ---------------------------------------------------------------------------
# Upload & Processing
# ---------------------------------------------------------------------------


@router.post("/sessions/{session_id}/upload", response_model=UploadResponse)
async def upload_files(
    session_id: str,
    files: Annotated[list[UploadFile], File(description="Documents to process")],
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload one or more files, process them, and return summaries.

    Supported formats: PDF, DOCX, PPTX, XLSX, and common image types.
    Max file size: 50 MB.  Max files per session: 10.
    """
    await _session_or_404(session_id, user, db)

    if not files:
        raise HTTPException(400, detail="No files provided")

    # Read all files into memory
    file_pairs: list[tuple[str, bytes]] = []
    upload_errors: list[str] = []

    for upload_file in files:
        filename = upload_file.filename or "unknown"

        # Extension pre-check (reject early, before reading bytes)
        if not converter.is_supported(filename):
            upload_errors.append(
                f"'{filename}': unsupported type. "
                f"Allowed: {', '.join(sorted(converter.ALLOWED_EXTENSIONS))}"
            )
            continue

        try:
            # Bounded read. save_original enforces the same limit, but only once the whole file
            # is already a bytes object in memory; asking for one byte more than the maximum
            # rejects an oversized upload without ever materialising it.
            content = await upload_file.read(session_manager.MAX_FILE_SIZE_BYTES + 1)
        except Exception as exc:
            upload_errors.append(f"'{filename}': could not read file — {exc}")
            continue

        if len(content) > session_manager.MAX_FILE_SIZE_BYTES:
            limit_mb = session_manager.MAX_FILE_SIZE_BYTES / 1024 / 1024
            upload_errors.append(f"'{filename}': larger than the {limit_mb:.0f} MB limit")
            continue

        if len(content) == 0:
            upload_errors.append(f"'{filename}': file is empty")
            continue

        file_pairs.append((filename, content))

    # Process valid files
    summaries: list[DocumentSummary] = []
    if file_pairs:
        summaries = await pipeline.process_files(session_id, file_pairs)
        # Refresh the RAG index so the chatbot can answer over the new documents.
        import asyncio

        from app.services.desk_research import rag_index

        await asyncio.to_thread(rag_index.rebuild_index, session_id)

    return UploadResponse(
        session_id=session_id,
        results=summaries,
        errors=upload_errors,
    )


# ---------------------------------------------------------------------------
# Document retrieval
# ---------------------------------------------------------------------------


@router.get(
    "/sessions/{session_id}/documents/{doc_id}",
    response_model=ProcessedDocument,
)
async def get_document(
    session_id: str, doc_id: str,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Get the full processed document including all blocks and markdown."""
    await _session_or_404(session_id, user, db)
    doc = session_manager.load_processed(session_id, doc_id)
    if not doc:
        raise HTTPException(404, detail="Document not found")
    return doc


@router.delete("/sessions/{session_id}/documents/{doc_id}", status_code=204)
async def delete_document(
    session_id: str, doc_id: str,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Remove one document from a session (its extracted JSON + images), then refresh the index."""
    await _session_or_404(session_id, user, db)
    session_manager.delete_document(session_id, doc_id)
    import asyncio

    from app.services.desk_research import rag_index

    await asyncio.to_thread(rag_index.rebuild_index, session_id)
    return Response(status_code=204)


@router.get(
    "/sessions/{session_id}/documents/{doc_id}/markdown",
)
async def get_document_markdown(
    session_id: str, doc_id: str,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Get the document's full markdown export as plain text."""
    from fastapi.responses import PlainTextResponse

    await _session_or_404(session_id, user, db)
    doc = session_manager.load_processed(session_id, doc_id)
    if not doc:
        raise HTTPException(404, detail="Document not found")
    return PlainTextResponse(content=doc.markdown, media_type="text/markdown")


# ---------------------------------------------------------------------------
# Executive Report Generation & Chat Q&A
# ---------------------------------------------------------------------------


class ReportRequest(BaseModel):
    title: str | None = Field(default=None, description="Optional custom session report title")
    language: str = Field(default="English", description="Target report language (English, Arabic, French)")
    user_context: str | None = Field(default=None, description="Optional user explanation/goal for what to focus on in these documents")


class ChatMessageIn(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    text: str = Field(default="", description="Message text")


class ChatRequest(BaseModel):
    query: str = Field(..., description="User question for the session documents")
    history: list[ChatMessageIn] = Field(
        default_factory=list, description="Recent conversation turns for follow-up context"
    )


@router.post("/sessions/{session_id}/report")
async def generate_session_report(
    session_id: str,
    body: ReportRequest = ReportRequest(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a comprehensive Executive Desk Research Synthesis Report across all session documents using Mistral LLM."""
    sess_info = await _session_or_404(session_id, user, db)

    docs: list[ProcessedDocument] = []
    for d_summary in sess_info.documents:
        p_doc = session_manager.load_processed(session_id, d_summary.doc_id)
        if p_doc:
            docs.append(p_doc)

    if not docs:
        raise HTTPException(400, detail="No processed documents found in this session.")

    from app.services.desk_research.synthesizer import get_synthesizer
    synthesizer = get_synthesizer()
    result = await synthesizer.generate_executive_report(
        documents=docs,
        session_title=body.title or sess_info.title or "Desk Research Session",
        language=body.language,
        user_context=body.user_context,
    )

    # Persist the report (and the goal that produced it) so it survives a reload.
    if result.get("status") == "success" and result.get("report_markdown"):
        session_manager.save_report(
            session_id,
            result["report_markdown"],
            user_context=body.user_context,
            title=body.title,
            cx_findings=result.get("cx_findings", []),
            document_analyses=result.get("document_analyses", []),
            report_overview=result.get("report_overview"),
        )
        # Fold the report into the RAG index so the chatbot can retrieve and cite it.
        import asyncio

        from app.services.desk_research import rag_index

        await asyncio.to_thread(rag_index.rebuild_index, session_id)
    return result



@router.post("/sessions/{session_id}/chat")
async def chat_session_documents(
    session_id: str,
    body: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Interactive Q&A chatbot endpoint querying uploaded session documents using Kimi / Gemini LLM."""
    sess_info = await _session_or_404(session_id, user, db)

    docs: list[ProcessedDocument] = []
    for d_summary in sess_info.documents:
        p_doc = session_manager.load_processed(session_id, d_summary.doc_id)
        if p_doc:
            docs.append(p_doc)

    if not docs:
        raise HTTPException(400, detail="No processed documents found in this session to chat with.")

    from app.services.desk_research.synthesizer import get_synthesizer
    synthesizer = get_synthesizer()
    result = await synthesizer.chat_with_session(
        documents=docs,
        query=body.query,
        chat_history=[m.model_dump() for m in body.history],
        session_id=session_id,
    )

    # Persist the turn so the conversation survives a page reload.
    import time
    from uuid import uuid4

    from app.schemas.desk_research import StoredChatMessage

    now = time.time() * 1000
    session_manager.append_chat(session_id, [
        StoredChatMessage(id=uuid4().hex[:12], role="user", text=body.query, ts=now),
        StoredChatMessage(
            id=uuid4().hex[:12], role="assistant",
            text=result.get("answer", ""), sources=result.get("sources", []), ts=now + 1,
        ),
    ])
    return result



