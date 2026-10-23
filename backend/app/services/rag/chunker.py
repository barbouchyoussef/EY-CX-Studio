"""Turn a processed document into retrieval-sized chunks.

Why a custom chunker (rather than docling's): our pipeline bypasses docling for digital PDFs
and discards the DoclingDocument otherwise, so docling's HybridChunker is not available. But we
already carry the structure it would rebuild -- typed ``DocumentBlock`` items with headings,
tables, captions, and page numbers -- which is a better substrate to chunk from.

The rules that make chunks good for RAG:
  * respect boundaries: never split a table or an image caption; break text on sentence ends;
  * right-size: pack text to a target length with a small sentence overlap so context that
    straddles a boundary is still retrievable;
  * carry citation metadata: filename, page, and the nearest heading travel with every chunk.
"""

from __future__ import annotations

import re
from uuid import uuid4

from app.schemas.desk_research import ProcessedDocument
from app.schemas.rag import RagChunk

# ~900 chars ≈ 200-250 tokens: small enough to be specific, large enough to hold a full point.
_TARGET_CHARS = 900
_OVERLAP_SENTENCES = 1
# A table wider/longer than this is split by rows so one giant sheet is not a single chunk.
_MAX_TABLE_CHARS = 1600

# Sentence boundary: Latin ., !, ?  plus Arabic full stop (؟ question, ۔ / period) and newlines.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?؟۔।])\s+|\n{2,}")


def _split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SENTENCE_SPLIT.split(text) if p and p.strip()]
    return parts


def _pack_text(text: str, target: int = _TARGET_CHARS, overlap: int = _OVERLAP_SENTENCES) -> list[str]:
    """Pack sentences into ~target-sized chunks with a small sentence overlap between them."""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= target:
        return [text]

    sentences = _split_sentences(text)
    chunks: list[str] = []
    cur: list[str] = []
    cur_len = 0

    for sent in sentences:
        # A single sentence longer than the target is hard-wrapped (rare: a table row, a URL run).
        if len(sent) > target:
            if cur:
                chunks.append(" ".join(cur))
                cur, cur_len = [], 0
            for i in range(0, len(sent), target):
                chunks.append(sent[i : i + target])
            continue

        if cur_len + len(sent) + 1 > target and cur:
            chunks.append(" ".join(cur))
            # Start the next chunk with the last `overlap` sentences for continuity.
            cur = cur[-overlap:] if overlap else []
            cur_len = sum(len(s) + 1 for s in cur)

        cur.append(sent)
        cur_len += len(sent) + 1

    if cur:
        chunks.append(" ".join(cur))
    # Drop any accidental empties and de-dupe consecutive identical chunks.
    out: list[str] = []
    for c in chunks:
        c = c.strip()
        if c and (not out or out[-1] != c):
            out.append(c)
    return out


def _table_to_text(table_data: list[dict] | None) -> str:
    """Render a table's row-dicts as compact 'col: value' lines the LLM can read and cite."""
    if not table_data:
        return ""
    lines: list[str] = []
    for row in table_data:
        cells = [f"{k}: {v}" for k, v in row.items() if v not in (None, "", "nan")]
        if cells:
            lines.append(" | ".join(cells))
    return "\n".join(lines)


def _mk_chunk(namespace: str, doc: ProcessedDocument, text: str, *, kind: str,
              page: int | None, heading: str | None, ordinal: int) -> RagChunk:
    return RagChunk(
        chunk_id=uuid4().hex[:16],
        namespace=namespace,
        source_id=doc.doc_id,
        source_name=doc.filename,
        text=text,
        kind=kind,
        page=page,
        heading=heading,
        ordinal=ordinal,
    )


def chunk_document(doc: ProcessedDocument, namespace: str) -> list[RagChunk]:
    """Chunk one processed document into retrievable units with citation metadata."""
    chunks: list[RagChunk] = []
    ordinal = 0
    current_heading: str | None = None
    text_buffer: list[str] = []
    buffer_page: int | None = None

    def flush_text() -> None:
        nonlocal ordinal, text_buffer, buffer_page
        if not text_buffer:
            return
        merged = "\n".join(text_buffer).strip()
        for piece in _pack_text(merged):
            chunks.append(_mk_chunk(namespace, doc, piece, kind="text",
                                    page=buffer_page, heading=current_heading, ordinal=ordinal))
            ordinal += 1
        text_buffer = []
        buffer_page = None

    for block in doc.blocks:
        btype = block.type

        if btype == "heading":
            flush_text()
            if block.text and block.text.strip():
                current_heading = block.text.strip()
            continue

        if btype == "table":
            flush_text()
            table_text = _table_to_text(block.table_data)
            if table_text:
                prefix = f"[Table — {current_heading}]\n" if current_heading else "[Table]\n"
                body = prefix + table_text
                # Keep small/medium tables whole; split only very large ones by row-packing.
                pieces = _pack_text(body, target=_MAX_TABLE_CHARS) if len(body) > _MAX_TABLE_CHARS else [body]
                for piece in pieces:
                    chunks.append(_mk_chunk(namespace, doc, piece, kind="table",
                                            page=block.page_number, heading=current_heading, ordinal=ordinal))
                    ordinal += 1
            continue

        if btype == "image":
            cap = (block.image_caption or "").strip()
            if cap:
                flush_text()
                loc = f"p{block.page_number}" if block.page_number else "figure"
                text = f"[Figure, {loc}] {cap}"
                chunks.append(_mk_chunk(namespace, doc, text, kind="caption",
                                        page=block.page_number, heading=current_heading, ordinal=ordinal))
                ordinal += 1
            continue

        # paragraph / list / code -> accumulate into the text buffer
        if block.text and block.text.strip():
            if buffer_page is None:
                buffer_page = block.page_number
            text_buffer.append(block.text.strip())

    flush_text()
    return chunks


def chunk_markdown(markdown: str, namespace: str, *, source_id: str, source_name: str) -> list[RagChunk]:
    """Chunk a raw markdown document (e.g. the generated executive report) into retrievable units.

    Tracks markdown headings as chunk context and packs body text to the same target size as
    document chunks, so the report is searchable and citable alongside the source documents.
    """
    chunks: list[RagChunk] = []
    ordinal = 0
    current_heading: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal ordinal, buffer
        if not buffer:
            return
        merged = "\n".join(buffer).strip()
        for piece in _pack_text(merged):
            chunks.append(RagChunk(
                chunk_id=uuid4().hex[:16], namespace=namespace, source_id=source_id,
                source_name=source_name, text=piece, kind="text", page=None,
                heading=current_heading, ordinal=ordinal,
            ))
            ordinal += 1
        buffer = []

    for raw in (markdown or "").split("\n"):
        line = raw.strip()
        heading = re.match(r"^(#{1,4})\s+(.*)$", line)
        if heading:
            flush()
            current_heading = heading.group(2).strip() or current_heading
            continue
        if line and line not in ("---", "***"):
            buffer.append(line)
    flush()
    return chunks


def chunk_documents(docs: list[ProcessedDocument], namespace: str) -> list[RagChunk]:
    """Chunk every document in a session, skipping failed/empty ones."""
    out: list[RagChunk] = []
    for doc in docs:
        if doc.status == "failed":
            continue
        out.extend(chunk_document(doc, namespace))
    return out
