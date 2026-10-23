"""Bridge between a Desk Research session and the shared RAG engine.

Keeps a session's retrieval index in sync with its documents. The only Desk-Research-specific
things here are (a) the namespace convention and (b) loading a session's ProcessedDocuments;
everything downstream (chunk → embed → store → retrieve) is the shared engine, so another module
reuses it by writing its own tiny bridge with a different namespace and loader.
"""

from __future__ import annotations

import logging

from app.core.text_normalization import repair_encoding
from app.schemas.desk_research import ProcessedDocument
from app.services.desk_research import session_manager
from app.services.rag import engine
from app.services.rag.chunker import chunk_documents, chunk_markdown

# Citation label + stable source id for the generated report inside the index.
REPORT_SOURCE_ID = "__executive_report__"
REPORT_SOURCE_NAME = "Executive Report"

logger = logging.getLogger(__name__)


def namespace_for(session_id: str) -> str:
    return f"desk_research:{session_id}"


def _load_session_docs(session_id: str) -> list[ProcessedDocument]:
    info = session_manager.get_session(session_id)
    if not info:
        return []
    docs: list[ProcessedDocument] = []
    for summary in info.documents:
        doc = session_manager.load_processed(session_id, summary.doc_id)
        if doc:
            docs.append(doc)
    return docs


def rebuild_index(session_id: str, documents: list[ProcessedDocument] | None = None) -> int:
    """(Re)build the session's index from its documents. Returns the chunk count."""
    ns = namespace_for(session_id)
    docs = documents if documents is not None else _load_session_docs(session_id)
    # Clean citation labels so retrieved sources aren't mojibake (heals pre-fix data too).
    for doc in docs:
        doc.filename = repair_encoding(doc.filename)
    chunks = chunk_documents(docs, ns)

    # Fold the generated executive report into the same index so the agent can retrieve and
    # cite it ("what did the report conclude about X?") alongside the source documents.
    info = session_manager.get_session(session_id)
    if info and info.report_markdown:
        chunks += chunk_markdown(
            repair_encoding(info.report_markdown), ns,
            source_id=REPORT_SOURCE_ID, source_name=REPORT_SOURCE_NAME,
        )

    try:
        return engine.build_index(ns, chunks)
    except Exception:
        logger.warning("Failed to build RAG index for %s", ns, exc_info=True)
        return 0


def ensure_index(session_id: str, documents: list[ProcessedDocument] | None = None) -> str:
    """Guarantee an index exists (lazy build for sessions created before RAG). Returns namespace."""
    ns = namespace_for(session_id)
    if not engine.has_index(ns):
        rebuild_index(session_id, documents)
    return ns


def delete_index(session_id: str) -> None:
    engine.delete_index(namespace_for(session_id))
