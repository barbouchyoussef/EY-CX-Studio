"""Orchestrates the full document processing flow.

    upload bytes → validate → save original → docling convert → extract → save result

Every step has its own error handling so a failure at any stage produces a
``ProcessedDocument`` with ``status="failed"`` and a human-readable error
message rather than an unhandled exception.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from app.schemas.desk_research import DocumentSummary, ProcessedDocument
from app.services.desk_research import converter, extractor, session_manager

logger = logging.getLogger(__name__)


async def process_file(
    session_id: str,
    filename: str,
    content: bytes,
) -> ProcessedDocument:
    """Process a single uploaded file end-to-end.

    This is the main entry point called by the API route.  It:

    1. Validates file extension and size.
    2. Saves the original to disk.
    3. Runs docling conversion in a thread pool.
    4. Extracts structured content from the docling result.
    5. Saves the ``ProcessedDocument`` JSON to disk.
    6. Returns the result (or a failed-status placeholder on error).

    This function **never raises** — all errors are captured into the
    returned document's ``errors`` list with ``status="failed"``.
    """
    from datetime import datetime, timezone
    from uuid import uuid4

    from app.core.text_normalization import repair_encoding

    # ── 0. Repair a mojibake filename before it touches disk or the LLM ──
    # Some clients send an Arabic/UTF-8 filename that arrives decoded as Latin-1
    # (e.g. "Ø§ÙØ¬ÙØ¯Ø©.pptx"); left as-is it corrupts the saved name, the report,
    # and every citation. This is a no-op on already-correct names.
    filename = repair_encoding(filename)

    # ── 1. Extension validation ──────────────────────────────────────
    if not converter.is_supported(filename):
        return _failed_doc(
            filename,
            f"Unsupported file type. Allowed: {', '.join(sorted(converter.ALLOWED_EXTENSIONS))}",
        )

    # ── 2. Save the original to durable storage (Supabase/disk via the adapter) ──
    try:
        session_manager.save_original(session_id, filename, content)
    except ValueError as exc:
        return _failed_doc(filename, str(exc))
    except Exception as exc:
        logger.exception("Failed to save original %s", filename)
        return _failed_doc(filename, f"Could not save file: {exc}")

    # The extractors (docling, native readers) need a REAL file on disk, not a storage key, so
    # materialize the bytes we already hold into a local temp file, process it, then delete it.
    # Ephemeral scratch is fine here -- it only has to survive this one request.
    import tempfile
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix)
    tmp.write(content)
    tmp.close()
    original_path = Path(tmp.name)
    try:
        return await _extract_and_persist(session_id, filename, original_path)
    finally:
        original_path.unlink(missing_ok=True)


async def _extract_and_persist(session_id: str, filename: str, original_path: Path) -> ProcessedDocument:
    """Steps 3-6: convert/extract from a local file, then persist the ProcessedDocument JSON.
    Never raises -- any failure becomes a failed-status document."""
    # ── 3. Route: digital PDFs (text layer) bypass docling entirely ──
    # Docling's page-image rendering is what exhausts memory on large PDFs; a PDF that
    # already has a text layer needs none of it, so it is read natively -- fast and crash-free.
    is_pdf = Path(filename).suffix.lower() == ".pdf"
    if is_pdf and converter.has_text_layer(original_path):
        images_dir = session_manager._images_dir(session_id, "temp")
        try:
            doc = await asyncio.to_thread(
                extractor.extract_pdf_native, original_path, filename, images_dir
            )
        except Exception as exc:
            logger.exception("Native PDF extraction failed for %s", filename)
            return _save_failed(session_id, filename, f"PDF extraction failed: {exc}")

        # Rename the temp images dir to the actual doc_id (mirrors the docling path).
        final_images_dir = session_manager._images_dir(session_id, doc.doc_id)
        if images_dir.exists() and images_dir != final_images_dir:
            try:
                if final_images_dir.exists():
                    import shutil
                    shutil.rmtree(final_images_dir)
                images_dir.rename(final_images_dir)
            except Exception:
                logger.warning("Could not rename images dir for %s", doc.doc_id)

        try:
            session_manager.save_processed(session_id, doc)
        except Exception as exc:
            logger.exception("Failed to save processed doc %s", doc.doc_id)
            doc.errors.append(f"Could not persist result: {exc}")
        return doc

    # ── 3b. Docling conversion for scans, images, and Office formats ──
    try:
        result = await asyncio.to_thread(converter.convert_file, original_path)
    except (ValueError, FileNotFoundError) as exc:
        return _save_failed(session_id, filename, str(exc))
    except RuntimeError as exc:
        return _save_failed(session_id, filename, str(exc))
    except Exception as exc:
        logger.exception("Unexpected conversion error for %s", filename)
        return _save_failed(session_id, filename, f"Conversion crashed: {exc}")

    # ── 4. Extract structured content ────────────────────────────────
    images_dir = session_manager._images_dir(session_id, "temp")
    try:
        # ``original_path`` is the only path that reliably exists at this point -- docling keeps
        # just the basename of what it converted -- and without it the OCR rescue cannot open the
        # file, so a scanned PDF comes back as image placeholders and nothing else.
        doc = extractor.extract(result, filename, images_dir=images_dir, source_path=original_path)
    except Exception as exc:
        logger.exception("Extraction failed for %s", filename)
        return _save_failed(session_id, filename, f"Content extraction failed: {exc}")

    # ── 5. Rename images dir to use actual doc_id ────────────────────
    final_images_dir = session_manager._images_dir(session_id, doc.doc_id)
    if images_dir.exists() and images_dir != final_images_dir:
        try:
            if final_images_dir.exists():
                import shutil
                shutil.rmtree(final_images_dir)
            images_dir.rename(final_images_dir)
        except Exception:
            logger.warning("Could not rename images dir for %s", doc.doc_id)

    # ── 6. Persist result ────────────────────────────────────────────
    try:
        session_manager.save_processed(session_id, doc)
    except Exception as exc:
        logger.exception("Failed to save processed doc %s", doc.doc_id)
        doc.errors.append(f"Could not persist result: {exc}")

    return doc


async def process_files(
    session_id: str,
    files: list[tuple[str, bytes]],
) -> list[DocumentSummary]:
    """Process multiple files concurrently within a session.

    Parameters
    ----------
    files
        List of ``(filename, content_bytes)`` tuples.

    Returns
    -------
    list[DocumentSummary]
        One summary per file, preserving input order.
    """
    tasks = [process_file(session_id, name, data) for name, data in files]
    results: list[ProcessedDocument] = await asyncio.gather(*tasks)

    return [
        DocumentSummary(
            doc_id=doc.doc_id,
            filename=doc.filename,
            format=doc.format,
            status=doc.status,
            page_count=doc.page_count,
            block_count=len(doc.blocks),
        )
        for doc in results
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _failed_doc(filename: str, error: str) -> ProcessedDocument:
    """Build a failed ``ProcessedDocument`` without touching disk."""
    from datetime import datetime, timezone
    from uuid import uuid4

    return ProcessedDocument(
        doc_id=uuid4().hex[:12],
        filename=filename,
        format=extractor._extension_to_format(filename),
        status="failed",
        errors=[error],
        processed_at=datetime.now(timezone.utc).isoformat(),
    )


def _save_failed(session_id: str, filename: str, error: str) -> ProcessedDocument:
    """Build a failed doc and attempt to save it so the session shows it."""
    doc = _failed_doc(filename, error)
    try:
        session_manager.save_processed(session_id, doc)
    except Exception:
        logger.warning("Could not persist failure record for %s", filename)
    return doc
