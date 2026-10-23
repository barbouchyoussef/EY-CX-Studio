"""Transforms a docling ``DoclingDocument`` into our own ``ProcessedDocument`` schema.

This module walks the docling document tree and produces a flat list of
``DocumentBlock`` items (headings, paragraphs, tables, images) together with
the full-document markdown export.

Every step is individually guarded — a crash in one element (e.g. a table that
can't be exported to a DataFrame) never prevents the rest of the document from
being extracted.
"""

from __future__ import annotations

import hashlib
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

# Images smaller than this in BOTH dimensions are decorative (icons, bullets, dividers) --
# not worth a vision call and only noise in the report.
_MIN_IMAGE_DIM = 100
# Bounded concurrency for figure captioning. Kept small so a free-tier VLM's rate limit is
# not tripped; the client rotates keys and backs off on 429 within this.
_VLM_MAX_WORKERS = 4

if TYPE_CHECKING:
    from docling.datamodel.document import ConversionResult

from app.schemas.desk_research import DocumentBlock, ProcessedDocument

logger = logging.getLogger(__name__)


def _safe_table_to_dicts(table_item, doc) -> list[dict] | None:
    """Export a docling ``TableItem`` to a list of row-dicts, or ``None``."""
    try:
        df = table_item.export_to_dataframe(doc)
        return df.to_dict(orient="records")
    except Exception:
        logger.warning("Could not export table to DataFrame", exc_info=True)
        return None



def _extension_to_format(filename: str) -> str:
    """Map a filename extension to a short format label."""
    ext = Path(filename).suffix.lower()
    mapping = {
        ".pdf": "pdf",
        ".docx": "docx",
        ".doc": "docx",
        ".pptx": "pptx",
        ".ppt": "pptx",
        ".xlsx": "xlsx",
        ".xls": "xlsx",
        ".png": "image",
        ".jpg": "image",
        ".jpeg": "image",
        ".tiff": "image",
        ".tif": "image",
        ".bmp": "image",
        ".webp": "image",
    }
    return mapping.get(ext, "unknown")


def _image_hash(pil_img) -> str:
    """Content hash of an image, so the same logo repeated on 20 slides is captioned once."""
    try:
        return hashlib.md5(pil_img.tobytes()).hexdigest()
    except Exception:
        return ""


def _is_decorative(pil_img) -> bool:
    """True for icons / bullets / dividers / banners -- shapes with no informational value.

    Beyond the tiny-in-both-dims case, this also drops the two shapes that were slipping through
    and getting pointlessly captioned: thin strips (header/footer rules) and extreme-aspect-ratio
    banners. Logos that pass this size gate are caught later by the VLM's DECORATIVE sentinel.
    """
    try:
        w, h = pil_img.size
        if max(w, h) < _MIN_IMAGE_DIM:          # tiny in both dims: icon / bullet
            return True
        if min(w, h) < 40:                       # a thin strip: divider or header/footer band
            return True
        if max(w, h) / max(1, min(w, h)) >= 7:   # extreme aspect ratio: banner / rule
            return True
        return False
    except Exception:
        return False


def _caption_unique_images(to_caption: dict[str, object]) -> dict[str, str | None]:
    """Caption a set of unique images (keyed by content hash) concurrently: VLM, then OCR.

    Bounded concurrency keeps a free-tier VLM's rate limit from tripping; the client rotates
    keys and backs off on 429 within this pool.
    """
    captions_by_hash: dict[str, str | None] = {}
    if not to_caption:
        return captions_by_hash

    from app.services.desk_research.gemini_vlm import get_vlm_client

    vlm = get_vlm_client()

    def _caption_one(pil_img) -> str | None:
        try:
            text = vlm.describe_image(pil_img)
        except Exception:
            text = None
        # The VLM flags logos/banners/icons it was asked to skip → drop them (no caption, no OCR).
        if text and text.strip().rstrip(".").upper() == "DECORATIVE":
            return None
        if not text or not text.strip():
            text = _ocr_image_text(pil_img)
        return text

    items = list(to_caption.items())
    with ThreadPoolExecutor(max_workers=min(_VLM_MAX_WORKERS, len(items))) as pool:
        for h, text in zip(
            (k for k, _ in items),
            pool.map(lambda kv: _caption_one(kv[1]), items),
        ):
            captions_by_hash[h] = text
    return captions_by_hash


def _build_image_blocks(entries: list[dict], images_dir: Path | None, filename: str) -> list[DocumentBlock]:
    """Turn raw image entries into captioned image blocks, cheaply.

    Shared by both extraction paths -- docling pictures and natively-harvested embedded
    images. Each entry is ``{"pil_img": PIL|None, "caption": str|None, "page_num": int|None}``.
    Three things keep this from making one vision-model call per image (a deck can hold 70+):
      - decorative images (logos, icons, bullets) are dropped, not described;
      - identical images (the logo on every slide) are hashed and described ONCE;
      - the surviving unique figures are captioned concurrently, bounded for a free-tier VLM.
    """
    from collections import defaultdict

    # Boilerplate detection: the SAME image appearing on many pages is a header/footer/logo/
    # watermark, not content -- drop it no matter what the VLM would make of it. This is what
    # removes the brand logo that otherwise gets transcribed once per page.
    pages_by_hash: dict[str, set[int]] = defaultdict(set)
    for entry in entries:
        pil = entry.get("pil_img")
        pn = entry.get("page_num")
        if pil is not None and pn is not None:
            h = _image_hash(pil)
            if h:
                pages_by_hash[h].add(pn)
    boilerplate = {h for h, pgs in pages_by_hash.items() if len(pgs) >= 3}

    records: list[dict] = []
    to_caption: dict[str, object] = {}  # hash -> pil_img, unique figures needing a caption

    for idx, entry in enumerate(entries):
        pil_img = entry.get("pil_img")
        caption = entry.get("caption")
        page_num = entry.get("page_num")

        image_path = None
        if images_dir is not None and pil_img is not None:
            try:
                images_dir.mkdir(parents=True, exist_ok=True)
                img_filename = f"figure_{idx:03d}.png"
                pil_img.save(str(images_dir / img_filename))
                image_path = img_filename
            except Exception:
                logger.warning("Could not save image %d from %s", idx, filename)

        img_hash = _image_hash(pil_img) if pil_img is not None else ""
        decorative = pil_img is not None and (_is_decorative(pil_img) or img_hash in boilerplate)
        has_caption = bool(caption and caption.strip())
        if pil_img is not None and not decorative and not has_caption and img_hash and img_hash not in to_caption:
            to_caption[img_hash] = pil_img

        records.append({
            "caption": caption,
            "image_path": image_path,
            "page_num": page_num,
            "hash": img_hash if not decorative else "",
            "decorative": decorative,
        })

    captions_by_hash = _caption_unique_images(to_caption)

    # Assemble blocks. A decorative image with no caption is noise -- drop it entirely.
    blocks: list[DocumentBlock] = []
    for rec in records:
        caption = rec["caption"]
        if (not caption or not caption.strip()) and rec["hash"]:
            caption = captions_by_hash.get(rec["hash"])
        if rec["decorative"] and not (caption and caption.strip()):
            continue
        blocks.append(
            DocumentBlock(
                type="image",
                image_path=rec["image_path"],
                image_caption=caption,
                page_number=rec["page_num"],
            )
        )
    return blocks


def _extract_pictures(doc, images_dir: Path | None, filename: str) -> list[DocumentBlock]:
    """Turn a docling document's pictures into captioned image blocks.

    Reads each picture's PIL image and any docling-provided caption, then hands the set to
    the shared :func:`_build_image_blocks` (filter → dedup → concurrent VLM→OCR).
    """
    if not hasattr(doc, "pictures"):
        return []

    entries: list[dict] = []
    for picture in doc.pictures:
        caption = None
        if hasattr(picture, "annotations"):
            for ann in picture.annotations:
                if getattr(ann, "text", None):
                    caption = ann.text
                    break
        if not caption and hasattr(picture, "caption_text"):
            try:
                caption = picture.caption_text(doc)
            except Exception:
                caption = None

        page_num = None
        if getattr(picture, "prov", None):
            page_num = getattr(picture.prov[0], "page_no", None)

        pil_img = None
        if images_dir:
            try:
                pil_img = picture.get_image(doc) if hasattr(picture, "get_image") else getattr(picture, "image", None)
            except Exception:
                pil_img = None

        entries.append({"pil_img": pil_img, "caption": caption, "page_num": page_num})

    return _build_image_blocks(entries, images_dir, filename)


# Bound on embedded images harvested from a single digital PDF: a cost/latency ceiling for the
# VLM on an image-heavy file (dedup happens after, so this caps *decoded* images, not captions).
_MAX_HARVEST_IMAGES = 60


def _decode_image_object(obj) -> "Image.Image | None":
    """One embedded image object as a PIL image, or None if it is too small or undecodable.

    Size is checked BEFORE decoding: an icon or a rule costs nothing to reject by its pixel
    dimensions, and decoding it would be wasted work on every page of every document.

    Failures are swallowed on purpose. A single malformed image object must not abort the harvest
    for the rest of the file -- one bad logo is not a reason to lose a document's charts.
    """
    try:
        width, height = obj.get_px_size()
        if max(width, height) < _MIN_IMAGE_DIM:
            return None
        return obj.get_bitmap(render=False).to_pil()
    except Exception:
        return None


def harvest_pdf_images(pdf_path: str | Path) -> list[dict]:
    """Pull embedded raster images out of a digital PDF WITHOUT rendering any page.

    This is the crucial distinction from docling: extracting an image *object* returns only
    that image's own bitmap (a chart, a screenshot), never a full-page render. So it stays
    memory-cheap and cannot std::bad_alloc the way docling's eager page rendering did. Tiny
    images are skipped by pixel size before they are even decoded.

    Returns a list of ``{"pil_img": PIL.Image, "page_num": int}`` in page order.
    """
    import pypdfium2 as pdfium
    import pypdfium2.raw as praw

    entries: list[dict] = []
    pdf = None
    try:
        pdf = pdfium.PdfDocument(str(pdf_path))
        for i in range(len(pdf)):
            if len(entries) >= _MAX_HARVEST_IMAGES:
                break
            page = pdf[i]
            try:
                for obj in page.get_objects(filter=(praw.FPDF_PAGEOBJ_IMAGE,)):
                    if len(entries) >= _MAX_HARVEST_IMAGES:
                        break
                    pil_img = _decode_image_object(obj)
                    if pil_img is not None:
                        entries.append({"pil_img": pil_img, "page_num": i + 1})
            finally:
                page.close()
    except Exception:
        logger.warning("Embedded image harvest failed for %s", pdf_path, exc_info=True)
    finally:
        if pdf is not None:
            pdf.close()
    return entries


def extract_pdf_native(pdf_path: str | Path, filename: str, images_dir: Path | None = None) -> ProcessedDocument:
    """Extract a digital (text-layer) PDF directly with pypdfium2, bypassing docling.

    docling renders every page to a bitmap for its layout/table/OCR models -- that rendering
    is what spiked memory and threw std::bad_alloc on the heavier Arabic pages. A PDF that
    already carries a text layer needs none of it: this reads the text in milliseconds, never
    crashes, and preserves Arabic far better than docling's own extraction did (1264 vs 177
    characters on the test report).

    When ``images_dir`` is given, embedded figures/charts are also harvested (without page
    rendering) and captioned through the same VLM→OCR pipeline docling uses, so a digital PDF
    no longer silently drops its visuals.
    """
    import pypdfium2 as pdfium

    doc_id = uuid4().hex[:12]
    blocks: list[DocumentBlock] = []
    md_parts: list[str] = []
    errors: list[str] = []
    page_count = 0
    pdf = None
    try:
        pdf = pdfium.PdfDocument(str(pdf_path))
        page_count = len(pdf)
        for i in range(page_count):
            try:
                text = pdf[i].get_textpage().get_text_range().strip()
            except Exception:
                text = ""
            if text:
                md_parts.append(f"### Page {i + 1}\n{text}")
                blocks.append(DocumentBlock(type="paragraph", text=text, page_number=i + 1))
    except Exception as exc:
        logger.exception("Native PDF extraction failed for %s", filename)
        errors.append(f"Native extraction error: {exc}")
    finally:
        if pdf is not None:
            pdf.close()

    # ── Mixed PDFs: OCR any page the text layer did not cover ──
    # A PDF routed here as "digital" can still contain scanned pages with no text layer (a text
    # cover + scanned appendices is common). Without this they are silently dropped. This renders
    # ONLY the uncovered pages, one at a time (memory-flat, capped), so the text pages stay fast
    # and the scanned pages inside the same file still get read.
    if page_count:
        _pre = len(blocks)
        try:
            _run_pdf_page_ocr_fallback(str(pdf_path), blocks, page_count)
        except Exception as exc:
            logger.warning("Per-page OCR fallback failed for %s", filename, exc_info=True)
            errors.append(f"Page OCR fallback failed: {exc}")
        # Fold the newly OCR'd pages into the markdown too (blocks feed RAG, markdown feeds the report).
        for b in blocks[_pre:]:
            if b.text:
                md_parts.append(f"### Page {b.page_number}\n{b.text}")

    # ── Harvest and caption embedded figures/charts (no page rendering) ──
    if images_dir is not None:
        try:
            harvested = harvest_pdf_images(pdf_path)
            img_blocks = _build_image_blocks(harvested, images_dir, filename)
            blocks.extend(img_blocks)
            cap_lines = [
                f"**[Figure, p{b.page_number}]:** {b.image_caption}"
                for b in img_blocks
                if b.image_caption and b.image_caption.strip()
            ]
            if cap_lines:
                md_parts.append("### Figures\n\n" + "\n\n".join(cap_lines))
        except Exception as exc:
            logger.warning("Image harvest/caption failed for %s", filename, exc_info=True)
            errors.append(f"Image extraction failed: {exc}")

    has_content = bool(blocks)
    markdown = _compact_table_markdown("\n\n".join(md_parts))
    return ProcessedDocument(
        doc_id=doc_id,
        filename=filename,
        format="pdf",
        status="success" if has_content else "failed",
        page_count=page_count or None,
        blocks=blocks,
        markdown=markdown,
        errors=errors if has_content else (errors or ["No extractable text in this PDF."]),
        processed_at=datetime.now(timezone.utc).isoformat(),
    )


# --------------------------------------------------------------------------------------------
# Rescue passes
# --------------------------------------------------------------------------------------------
# docling occasionally returns almost nothing for a file it nominally supports. Rather than ship
# an empty document, two cheap native readers run as a fallback. They are separate functions
# because inlining them put extract() at nesting depth 10, where the actual work is five levels
# below the line that decides whether to do it.

# Below this much markdown, docling is treated as having under-extracted.
_THIN_OUTPUT_CHARS = 500


def _locate_original(
    result: "ConversionResult",
    images_dir: Path | None,
    filename: str,
    source_path: Path | str | None = None,
) -> str | None:
    """Where the uploaded file actually sits on disk, or None if it cannot be found.

    Returning None disables BOTH rescue passes, so a scanned PDF comes back as nothing but
    ``<!-- image -->`` placeholders. Every candidate below has failed that way in production, so
    the caller's own path is tried first and the rest are kept only as fallbacks:

      * ``source_path`` -- what the caller actually converted. The pipeline writes the upload to
        a temp file and holds that path, so this is the only candidate guaranteed to exist.
      * ``result.input.file`` -- docling records the BASENAME only (``PureWindowsPath('tmp1234
        .pdf')``), so it resolves against the CWD and essentially never exists. Kept for direct
        callers that happen to convert a file in the working directory.
      * ``originals/`` -- the session's stored upload, two levels above the per-doc images dir
        (``<session>/images/<doc_id>``), not one.
    """
    if source_path and Path(source_path).exists():
        return str(source_path)
    candidate = getattr(getattr(result, "input", None), "file", None)
    if candidate and Path(candidate).exists():
        return str(candidate)
    if images_dir:
        stored = images_dir.parent.parent / "originals" / filename
        if stored.exists():
            return str(stored)
    if Path(filename).exists():
        return filename
    return None


def _rescue_pdf_text(pdf_path: str, blocks: list[DocumentBlock], covered_pages: set[int]) -> list[str]:
    """Read the text layer of pages docling missed, appending a block per page.

    Mutates `blocks` and `covered_pages` so the OCR pass that follows can skip whatever this
    recovered. Returns the markdown fragments for the caller to append.
    """
    lines: list[str] = []
    try:
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(pdf_path)
        try:
            for index in range(len(pdf)):
                page_no = index + 1
                if page_no in covered_pages:
                    continue
                text = pdf[index].get_textpage().get_text_range().strip()
                if not text:
                    continue
                lines.append(f"\n### Page {page_no}\n{text}")
                blocks.append(DocumentBlock(type="paragraph", text=text, page_number=page_no))
                covered_pages.add(page_no)
        finally:
            pdf.close()
    except Exception as exc:
        logger.warning("pypdfium2 native text extraction failed: %s", exc)
    return lines


def _slide_text_lines(slide) -> list[str]:
    """Every readable line on one slide: text-frame paragraphs and table rows."""
    lines: list[str] = []
    for shape in slide.shapes:
        if shape.has_text_frame:
            lines.extend(p.text.strip() for p in shape.text_frame.paragraphs if p.text.strip())
        elif shape.has_table:
            for row in shape.table.rows:
                lines.append(" | ".join(cell.text.strip() for cell in row.cells))
    return lines


def _rescue_pptx_text(pptx_path: str, blocks: list[DocumentBlock]) -> list[str]:
    """Read a deck slide by slide, appending a block per slide that has content."""
    lines: list[str] = []
    try:
        from pptx import Presentation

        for index, slide in enumerate(Presentation(pptx_path).slides, 1):
            slide_lines = _slide_text_lines(slide)
            if not slide_lines:
                continue
            text = "\n".join(slide_lines)
            lines.append(f"\n### Slide {index}\n{text}")
            blocks.append(DocumentBlock(type="paragraph", text=text, page_number=index))
    except Exception as exc:
        logger.warning("python-pptx native extraction failed: %s", exc)
    return lines


def _caption_images_in_markdown(markdown: str, blocks: list[DocumentBlock]) -> str:
    """Put each image's description where docling left a bare `<!-- image -->` placeholder.

    Positional: the nth placeholder gets the nth captioned image, because docling emits them in
    document order. Replacing one at a time keeps that alignment.
    """
    captioned = [b for b in blocks if b.type == "image" and b.image_caption]
    if not captioned or "<!-- image -->" not in markdown:
        return markdown
    for image in captioned:
        caption = f"**[Image {image.image_path or ''}]:** {image.image_caption}"
        markdown = markdown.replace("<!-- image -->", caption, 1)
    return markdown


def _rescue_thin_extraction(
    markdown: str,
    *,
    result: "ConversionResult",
    filename: str,
    blocks: list[DocumentBlock],
    page_count: int | None,
    images_dir: Path | None,
    source_path: Path | str | None = None,
) -> str:
    """Fill in what docling missed, without repeating what it found.

    Two independent layers, and both are deliberately conditional -- a normal digital PDF, where
    docling works, triggers neither:

      * a **native read** (pypdfium2 for PDFs, python-pptx for decks) when docling's own output
        came back suspiciously thin, covering only the pages it did not already reach;
      * **per-page OCR** for pages that still have no text after all that, which is the definition
        of a scanned page.

    Each appends to the markdown rather than replacing it, so a rescue supplements docling and
    never overwrites a better extraction.
    """
    lower = filename.lower()

    if lower.endswith(".pdf"):
        source_pdf = _locate_original(result, images_dir, filename, source_path)
        if not source_pdf:
            # Silence here is what let a 4-page dashboard PDF through as three image
            # placeholders, marked successful. If the file cannot be found, say so.
            logger.warning(
                "Cannot locate the original of %s -- skipping both rescue passes. A scanned or "
                "image-only file will come back with no text.", filename,
            )
            return markdown

        if len(markdown.strip()) < _THIN_OUTPUT_CHARS:
            covered_pages = {b.page_number for b in blocks if b.page_number and (b.text or b.table_data)}
            rescued = _rescue_pdf_text(source_pdf, blocks, covered_pages)
            if rescued:
                markdown = (markdown + "\n" + "\n".join(rescued)).strip()

        # Whatever still has no text is genuinely scanned, so OCR those pages and only those.
        before = len(blocks)
        _run_pdf_page_ocr_fallback(source_pdf, blocks, page_count)
        ocr_lines = [f"\n### Page {b.page_number}\n{b.text}" for b in blocks[before:] if b.text]
        if ocr_lines:
            markdown = (markdown + "\n" + "\n".join(ocr_lines)).strip()
        return markdown

    if lower.endswith(".pptx") and len(markdown.strip()) < _THIN_OUTPUT_CHARS:
        source_pptx = _locate_original(result, images_dir, filename, source_path)
        if source_pptx:
            rescued = _rescue_pptx_text(source_pptx, blocks)
            if rescued:
                markdown = (markdown + "\n" + "\n".join(rescued)).strip()

    return markdown


def extract(
    result: "ConversionResult",
    filename: str,
    images_dir: Path | None = None,
    source_path: Path | str | None = None,
) -> ProcessedDocument:
    """Extract structured content from a docling ``ConversionResult``.

    Parameters
    ----------
    result
        The output of ``converter.convert()``.
    filename
        Original filename (used for metadata).
    images_dir
        If provided, extracted images are saved here and their relative
        paths are stored in the ``DocumentBlock.image_path`` field.
    source_path
        The file that was converted. Pass it whenever you have it: the rescue passes (native
        text read, per-page OCR) can only run on a file they can open, and docling's own record
        of the path keeps just the basename. Without this a scanned PDF silently yields nothing.

    Returns
    -------
    ProcessedDocument
        Our unified document schema with blocks, markdown, and metadata.
    """
    from docling.datamodel.base_models import ConversionStatus

    doc_id = uuid4().hex[:12]
    errors: list[str] = []
    blocks: list[DocumentBlock] = []

    # ── Status mapping ───────────────────────────────────────────────
    if result.status == ConversionStatus.SUCCESS:
        status = "success"
    elif result.status == ConversionStatus.PARTIAL_SUCCESS:
        status = "partial"
        for err in result.errors or []:
            errors.append(str(err))
    else:
        status = "failed"
        for err in result.errors or []:
            errors.append(str(err))
        return ProcessedDocument(
            doc_id=doc_id,
            filename=filename,
            format=_extension_to_format(filename),
            status=status,
            errors=errors,
            processed_at=datetime.now(timezone.utc).isoformat(),
        )

    doc = result.document

    # Page count comes first now: the markdown below is exported per page, so it has to know how
    # many there are.
    page_count = None
    try:
        if hasattr(doc, "pages") and doc.pages:
            page_count = len(doc.pages)
    except Exception:
        pass

    markdown = ""
    try:
        markdown = _markdown_with_page_headers(doc, page_count, filename)
    except Exception:
        logger.warning("Markdown export failed for %s", filename, exc_info=True)
        errors.append("Full markdown export failed")

    try:
        _extract_items(doc, blocks, errors, images_dir)
    except Exception:
        logger.exception("Document tree walk failed for %s", filename)
        errors.append("Document tree extraction failed partially")

    # ── Extract tables separately (docling stores them as top-level) ─
    try:
        if hasattr(doc, "tables"):
            for table in doc.tables:
                table_data = _safe_table_to_dicts(table, doc)
                page_num = None
                if hasattr(table, "prov") and table.prov:
                    page_num = getattr(table.prov[0], "page_no", None)
                blocks.append(
                    DocumentBlock(
                        type="table",
                        table_data=table_data,
                        page_number=page_num,
                    )
                )
    except Exception:

        logger.warning("Table extraction failed for %s", filename, exc_info=True)
        errors.append("Some tables could not be extracted")

    # ── Extract pictures (filtered, de-duplicated, captioned concurrently) ──
    try:
        blocks.extend(_extract_pictures(doc, images_dir, filename))
    except Exception:
        logger.warning("Picture extraction failed for %s", filename, exc_info=True)
        errors.append("Some images could not be extracted")

    # ── Replace <!-- image --> placeholders with the captions the VLM wrote ──
    try:
        markdown = _caption_images_in_markdown(markdown, blocks)
    except Exception:
        logger.warning("Image captioning failed for %s", filename, exc_info=True)

    # ── Rescue passes, guarded on their own ──────────────────────────
    # Their own try on purpose. These are the fallback layers the module leans on for scanned and
    # awkward files, and they used to share a guard with the captioning above -- so a failure
    # there took them out silently, and the file came back thin for a reason nothing recorded.
    try:
        markdown = _rescue_thin_extraction(
            markdown,
            result=result,
            filename=filename,
            blocks=blocks,
            page_count=page_count,
            images_dir=images_dir,
            source_path=source_path,
        )
    except Exception:
        logger.warning("Rescue extraction failed for %s", filename, exc_info=True)

    # Collapse over-wide sparse tables (spreadsheets especially) so the report context is
    # real data, not thousands of empty cells.
    try:
        markdown = _compact_table_markdown(markdown)
    except Exception:
        logger.warning("Table compaction failed for %s", filename, exc_info=True)

    # ── A document nothing could be read from must SAY so ────────────
    # Docling reports SUCCESS for a file it turned into nothing but image placeholders, and
    # everything downstream then treats it as a document with content: it is counted as
    # "analysed", and the deep-dive model is handed a title with no text under it and writes
    # something anyway. Recording it as partial is what lets the synthesizer skip it.
    if not has_readable_text(markdown):
        status = "partial" if status == "success" else status
        errors.append(NO_TEXT_ERROR)
        logger.warning(
            "No readable text extracted from %s (%s pages). It is most likely a scanned or "
            "image-only file that OCR could not read.", filename, page_count,
        )

    return ProcessedDocument(
        doc_id=doc_id,
        filename=filename,
        format=_extension_to_format(filename),
        status=status,
        page_count=page_count,
        blocks=blocks,
        markdown=markdown,
        errors=errors,
        processed_at=datetime.now(timezone.utc).isoformat(),
    )


def _is_table_line(line: str) -> bool:
    s = line.strip()
    return len(s) >= 2 and s.startswith("|") and s.endswith("|")


def _table_cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip()[1:-1].split("|")]


def _is_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(c and set(c) <= {"-", ":", " "} for c in cells)


def _compact_table_markdown(markdown: str, max_cols: int = 40) -> str:
    """Trim rendered markdown tables to their populated column extent.

    A spreadsheet whose used-range reaches column 370 makes docling emit 370 cells on every
    row, almost all empty -- 1.18M characters for a handful of real columns, which would then
    dominate the report's context. This truncates each table to the rightmost column that
    actually holds data (capped for safety) and drops fully-empty rows, without touching
    non-table text.
    """
    if "|" not in markdown:
        return markdown
    lines = markdown.splitlines()
    out: list[str] = []
    i, n = 0, len(lines)
    while i < n:
        if not _is_table_line(lines[i]):
            out.append(lines[i])
            i += 1
            continue
        # Gather one contiguous table block.
        block = []
        while i < n and _is_table_line(lines[i]):
            block.append(lines[i])
            i += 1
        rows = [_table_cells(l) for l in block]
        rightmost = 0
        for r in rows:
            if _is_separator_row(r):
                continue
            for idx, cell in enumerate(r):
                if cell:
                    rightmost = max(rightmost, idx)
        width = min(rightmost + 1, max_cols)
        for r in rows:
            trimmed = r[:width]
            if not _is_separator_row(trimmed) and not any(trimmed):
                continue  # drop a fully-empty row
            out.append("| " + " | ".join(trimmed) + " |")
    return "\n".join(out)


def _extract_items(doc, blocks: list[DocumentBlock], errors: list[str], images_dir: Path | None) -> None:
    """Walk the document body items and build text/heading/list blocks."""
    if not hasattr(doc, "iterate_items"):
        return

    try:
        for item_tuple in doc.iterate_items():
            item = item_tuple[0] if isinstance(item_tuple, tuple) else item_tuple
            level = item_tuple[1] if isinstance(item_tuple, tuple) and len(item_tuple) > 1 else None
            try:
                _process_item(item, level, doc, blocks)
            except Exception:
                continue
    except Exception:
        logger.warning("Error during iterate_items traversal", exc_info=True)


# Below this share of the single-call export, the per-page split is assumed to have lost content
# and the plain export is used instead. Page headers are worth having; a shorter document is not
# worth them.
_PAGE_SPLIT_MIN_RATIO = 0.8


def _markdown_with_page_headers(doc, page_count: int | None, filename: str) -> str:
    """Docling's markdown, split per page and headed with the page number.

    ``export_to_markdown()`` renders the whole document as one string with nothing marking where
    one page ends and the next begins, so a finding drawn from it cannot be traced back to a page.
    The native text-layer path already emits ``### Page N``; this gives the docling path the same
    shape. It re-exports per page through docling's own renderer rather than rebuilding from
    blocks, so tables and structure come out exactly as they did before.

    Page numbers are docling's own, read from ``doc.pages``, not counted -- a page that renders
    empty therefore cannot shift the numbering of every page after it.

    Falls back to the single-call export whenever per-page export is unavailable, raises, or
    returns materially less text. A document with page headers is better; one without them is what
    shipped before and has to keep working.
    """
    whole = doc.export_to_markdown()
    if not page_count or page_count < 2:
        return whole

    try:
        parts: list[str] = []
        content_chars = 0
        for page_no in sorted(doc.pages):
            page_md = (doc.export_to_markdown(page_no=page_no) or "").strip()
            if not page_md:
                continue
            content_chars += len(page_md)
            parts.append(f"### Page {page_no}\n{page_md}")
    except Exception:
        logger.warning(
            "Per-page markdown export failed for %s; using the whole-document export",
            filename, exc_info=True,
        )
        return whole

    if not parts or content_chars < len(whole) * _PAGE_SPLIT_MIN_RATIO:
        logger.warning(
            "Per-page export of %s gave %d chars against %d for the whole document; "
            "using the whole-document export",
            filename, content_chars, len(whole),
        )
        return whole

    return "\n\n".join(parts)


def _item_page(item) -> int | None:
    """Best-effort page number for a docling item, from its provenance."""
    try:
        if getattr(item, "prov", None):
            return getattr(item.prov[0], "page_no", None)
    except Exception:
        pass
    return None


def _process_item(item, level, doc, blocks: list[DocumentBlock]) -> None:
    """Process a single document item into a DocumentBlock."""
    item_type = type(item).__name__

    # Skip table and picture items here (they are handled in dedicated steps)
    if "TableItem" in item_type or "PictureItem" in item_type or "GroupItem" in item_type:
        return

    page = _item_page(item)  # so page-coverage tracking works for the rescue passes

    # Section headers
    if "SectionHeader" in item_type or "Heading" in item_type or "Title" in item_type:
        h_level = getattr(item, "level", level or 1)
        text = _get_text(item, doc)
        if text and text.strip():
            blocks.append(DocumentBlock(type="heading", level=h_level, text=text.strip(), page_number=page))
        return

    # List items
    if "ListItem" in item_type or "List" in item_type:
        text = _get_text(item, doc)
        if text and text.strip():
            blocks.append(DocumentBlock(type="list", text=text.strip(), page_number=page))
        return

    # Code blocks
    if "Code" in item_type:
        text = _get_text(item, doc)
        if text and text.strip():
            blocks.append(DocumentBlock(type="code", text=text.strip(), page_number=page))
        return

    # Text / Paragraph items
    if "TextItem" in item_type or hasattr(item, "text"):
        text = _get_text(item, doc)
        if text and text.strip():
            blocks.append(DocumentBlock(type="paragraph", text=text.strip(), page_number=page))



def _get_text(item, doc) -> str | None:
    """Safely extract text from a docling item."""
    # Try export_to_text method first (most reliable)
    if hasattr(item, "export_to_markdown"):
        try:
            return item.export_to_markdown(doc)
        except Exception:
            pass
    if hasattr(item, "text"):
        return item.text
    return str(item) if item else None


_OCR_READER = None

def _ocr_image_text(pil_img) -> str | None:
    """Fallback: extract text inside an image using EasyOCR when VLM description is empty."""
    global _OCR_READER
    try:
        import numpy as np
        import easyocr

        if _OCR_READER is None:
            # Same EasyOCR language constraint as the converter -- reuse its resolved set so
            # Arabic and French are never combined (which throws at reader construction).
            from app.services.desk_research.converter import OCR_LANGS
            _OCR_READER = easyocr.Reader(OCR_LANGS, gpu=False)


        # Scale small images up for clarity, downscale huge images to max 1200px for speed & memory safety
        w, h = pil_img.size
        if w > 1200 or h > 1200:
            scale = 1200.0 / max(w, h)
            scaled_img = pil_img.resize((int(w * scale), int(h * scale)))
        elif w < 600 or h < 600:
            scaled_img = pil_img.resize((w * 2, h * 2))
        else:
            scaled_img = pil_img

        img_np = np.array(scaled_img)
        # canvas_size caps the internal image EasyOCR allocates for detection (default 2560,
        # the source of the std::bad_alloc); batch_size=1 keeps recognition memory flat.
        results = _OCR_READER.readtext(img_np, canvas_size=1280, mag_ratio=1.0, batch_size=1)

        texts = [res[1].strip() for res in results if res[2] > 0.15 and res[1].strip()]
        return " | ".join(texts) if texts else None
    except Exception:
        logger.warning("EasyOCR fallback failed for image", exc_info=True)
        return None


# Rendering a full page to a bitmap for OCR is the most memory-hungry step in the whole
# pipeline (a scanned A4 at scale 2.0 is ~14 MP). On a long scanned PDF -- especially two
# uploaded at once -- that spiked memory enough to abort the conversion (the std::bad_alloc
# seen on the Arabic reports). A lower scale and a page cap keep it bounded.
_OCR_PAGE_RENDER_SCALE = 1.5
_MAX_OCR_FALLBACK_PAGES = 25


# What a document is left with when docling saw only pictures and every rescue came up empty.
NO_TEXT_ERROR = "No readable text could be extracted from this file."

# Markdown that carries no information: docling's picture placeholder, the page/slide headers
# this module adds itself, and table rules. A file made only of these has nothing to analyse.
_EMPTY_MARKDOWN_RE = re.compile(
    r"(<!--\s*image\s*-->)|(^#{1,6}\s*(page|slide)\s*\d+\s*$)|(^[|\s:-]+$)",
    re.IGNORECASE | re.MULTILINE,
)

# Below this many real characters there is nothing a model could honestly summarise. A title
# page alone clears it; three image placeholders do not.
_MIN_READABLE_CHARS = 40


def has_readable_text(markdown: str | None) -> bool:
    """True if *markdown* contains prose rather than only structural noise.

    Used to tell "this document had no text" apart from "this document was not processed", which
    docling's own SUCCESS status does not distinguish.
    """
    if not markdown:
        return False
    return len(_EMPTY_MARKDOWN_RE.sub(" ", markdown).strip()) >= _MIN_READABLE_CHARS


def _run_pdf_page_ocr_fallback(pdf_path: str, blocks: list[DocumentBlock], page_count: int | None = None) -> None:
    """Fallback for visual PDFs: OCR the pages that have no text yet, one page at a time,
    releasing each page bitmap before rendering the next so memory stays flat."""
    pdf = None
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(pdf_path)

        # "Covered" for TEXT recovery means the page already has real text or a table -- NOT merely
        # an image caption. A vector/image-only page (e.g. a dashboard exported as pictures) gets a
        # VLM caption but no data; excluding image_caption here is what lets OCR read its real text.
        covered_pages = {
            b.page_number for b in blocks if b.page_number and (b.text or b.table_data)
        }
        uncovered = [i for i in range(len(pdf)) if (i + 1) not in covered_pages][:_MAX_OCR_FALLBACK_PAGES]

        for i in uncovered:
            page_no = i + 1
            pil_img = None
            try:
                pil_img = pdf[i].render(scale=_OCR_PAGE_RENDER_SCALE).to_pil()
                ocr_text = _ocr_image_text(pil_img)
                if ocr_text:
                    blocks.append(
                        DocumentBlock(type="paragraph", text=f"[Page {page_no} OCR]: {ocr_text}", page_number=page_no)
                    )
            except Exception:
                # A single page that can't be rendered/OCR'd (e.g. transient OOM) must not
                # abort the whole document -- skip it and keep going.
                logger.warning("Page %d OCR fallback failed for %s", page_no, pdf_path)
            finally:
                if pil_img is not None:
                    pil_img.close()
    except Exception:
        logger.warning("PDF page OCR fallback failed for %s", pdf_path, exc_info=True)
    finally:
        if pdf is not None:
            pdf.close()





