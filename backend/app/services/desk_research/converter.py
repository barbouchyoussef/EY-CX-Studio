"""Docling-based document converter with multilingual OCR and Pixtral VLM.

Wraps IBM's docling library to convert PDF, DOCX, PPTX, XLSX, and image files
into a unified ``DoclingDocument`` representation.  The converter is configured
once per worker and reused across requests.

Key design decisions
--------------------
* **One shared instance** — ``DocumentConverter`` is expensive to construct
  (loads layout and table models).  We build it lazily on first use and cache it.
* **Thread-pool execution** — docling is synchronous; we run conversions in
  ``asyncio.to_thread`` so the event loop stays responsive.
* **Multilingual OCR** — EasyOCR is configured for Arabic, French, and English.
* **Pixtral VLM** — Image captioning uses Mistral's Pixtral model via the
  existing ``MISTRAL_API_KEY`` so no new credentials are needed.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from docling.datamodel.document import ConversionResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Allowed extensions → docling InputFormat mapping
# ---------------------------------------------------------------------------

_EXT_TO_FORMAT: dict[str, str] = {
    ".pdf": "PDF",
    ".docx": "DOCX",
    ".doc": "DOCX",
    ".pptx": "PPTX",
    ".ppt": "PPTX",
    ".xlsx": "XLSX",
    ".xls": "XLSX",
    ".png": "IMAGE",
    ".jpg": "IMAGE",
    ".jpeg": "IMAGE",
    ".tiff": "IMAGE",
    ".tif": "IMAGE",
    ".bmp": "IMAGE",
    ".webp": "IMAGE",
}

ALLOWED_EXTENSIONS = frozenset(_EXT_TO_FORMAT.keys())


# ---------------------------------------------------------------------------
# OCR language selection
# ---------------------------------------------------------------------------
# EasyOCR groups scripts: Arabic ("ar") is ONLY compatible with English and other
# Arabic-family scripts (fa/ur/ug) -- it CANNOT be combined with Latin languages like
# French. The original config asked for ["en","ar","fr"], which makes the reader throw at
# construction time, so every PDF and image crashed before a page was read.
#
# Because you cannot OCR Arabic and French in one pass, the pair is a deliberate choice,
# overridable via DESK_OCR_LANGS. Default is Arabic+English: scanned Arabic documents are
# the case that genuinely NEEDS OCR (no text layer), while French/English digital PDFs get
# their text from the native text-layer pass regardless of the OCR language.
_ARABIC_FAMILY = {"ar", "fa", "ur", "ug"}


def _resolve_ocr_langs() -> list[str]:
    import os

    raw = os.getenv("DESK_OCR_LANGS", "ar,en")
    langs = [x.strip().lower() for x in raw.split(",") if x.strip()]
    if not langs:
        langs = ["ar", "en"]
    # Guard against an invalid mix silently reintroducing the crash: if any Arabic-family
    # script is present, keep only Arabic-family + English.
    if any(l in _ARABIC_FAMILY for l in langs):
        langs = [l for l in langs if l in _ARABIC_FAMILY or l == "en"]
        if "en" not in langs:
            langs.append("en")
    return langs


OCR_LANGS = _resolve_ocr_langs()


def is_supported(filename: str) -> bool:
    """Return True if *filename* has an extension we can process."""
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def has_text_layer(pdf_path: str | Path, sample_pages: int = 6, min_chars: int = 120) -> bool:
    """True if the PDF carries an embedded text layer (i.e. it is a digital PDF, not a scan).

    Such PDFs need no OCR and no layout-model rendering: their text can be read directly,
    which avoids docling's memory-heavy preprocessing (the std::bad_alloc seen on Arabic
    reports) and, for Arabic especially, extracts the script more faithfully.
    """
    try:
        import pypdfium2 as pdfium
    except Exception:
        return False
    pdf = None
    try:
        pdf = pdfium.PdfDocument(str(pdf_path))
        total = 0
        for i in range(min(len(pdf), sample_pages)):
            total += len(pdf[i].get_textpage().get_text_range().strip())
            if total >= min_chars:
                return True
        return total >= min_chars
    except Exception:
        return False
    finally:
        if pdf is not None:
            pdf.close()


# ---------------------------------------------------------------------------
# Lazy builder — called once, cached forever
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _build_converter():
    """Build and cache a ``DocumentConverter`` with production-grade options.

    Imports are deferred so the heavy docling import only happens when the
    first conversion is actually requested.
    """
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import (
        EasyOcrOptions,
        PdfPipelineOptions,
        TableFormerMode,
        TableStructureOptions,
    )
    from docling.document_converter import DocumentConverter, PdfFormatOption

    # ── PDF pipeline (also used for images) ──────────────────────────
    pdf_opts = PdfPipelineOptions()
    pdf_opts.do_ocr = True
    pdf_opts.do_table_structure = True
    pdf_opts.ocr_options = EasyOcrOptions(lang=OCR_LANGS)
    pdf_opts.table_structure_options = TableStructureOptions(mode=TableFormerMode.FAST)
    pdf_opts.generate_picture_images = False
    pdf_opts.images_scale = 1.0
    pdf_opts.do_picture_description = False


    # ── Format options ───────────────────────────────────────────────
    format_options = {
        InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_opts),
        InputFormat.IMAGE: PdfFormatOption(pipeline_options=pdf_opts),
    }

    converter = DocumentConverter(format_options=format_options)
    logger.info("DocumentConverter initialised (EasyOCR %s, TableFormer FAST)", "+".join(OCR_LANGS))
    return converter


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def convert_file(file_path: str | Path) -> "ConversionResult":
    """Convert a single file and return the docling ``ConversionResult``."""
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = file_path.suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{ext}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    converter = _build_converter()
    logger.info("Converting %s (%s)", file_path.name, ext)

    try:
        result = converter.convert(str(file_path))
    except Exception as exc:
        logger.exception("Docling conversion failed for %s", file_path.name)
        raise RuntimeError(f"Document conversion failed: {exc}") from exc

    return result
