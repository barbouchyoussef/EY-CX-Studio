"""Shared schemas for the reusable RAG engine.

These types are deliberately module-agnostic: Desk Research is the first consumer, but Social,
Assessment, etc. feed the same engine by producing ``RagChunk`` items under their own namespace.
The only thing that changes per module is the *source of the chunks* -- the retrieval, storage,
and answering are shared.
"""

from __future__ import annotations

from pydantic import BaseModel


class RagChunk(BaseModel):
    """One retrievable unit of text with the metadata needed to cite it."""

    chunk_id: str
    namespace: str          # e.g. "desk_research:<session_id>" -- the retrieval scope
    source_id: str          # id of the origin object (e.g. a document's doc_id)
    source_name: str        # human label for citations (e.g. the filename)
    text: str               # the chunk's content (what gets embedded and shown to the LLM)
    kind: str = "text"      # "text" | "table" | "caption"
    page: int | None = None
    heading: str | None = None   # nearest preceding heading, for context
    ordinal: int = 0        # position within its source, to keep stable ordering


class RetrievedChunk(BaseModel):
    """A chunk returned from retrieval, with its similarity score."""

    chunk: RagChunk
    score: float
