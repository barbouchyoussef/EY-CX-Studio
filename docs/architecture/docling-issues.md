# Docling issues encountered (candidate upstream contributions)

Notes collected while building the Desk Research module. Each entry has a concrete symptom,
a reproduction, the root cause as we understood it, and a proposed fix. Versions/paths refer
to the docling install in this project's `backend/.venv`.

---

## 1. Incompatible OCR language set crashes late, with a cryptic error

**Severity:** low effort, high annoyance — good first contribution.

**Symptom.** Configuring EasyOCR with an Arabic + Latin language mix does not fail when the
options are built. It fails much later, deep inside `convert()`, at EasyOCR reader
construction:

```
ValueError: Arabic is only compatible with English, try lang_list=["ar","fa","ur","ug","en"]
```

Every PDF and image "crashes" even though the real problem is a static config mistake.

**Reproduction.**
```python
from docling.datamodel.pipeline_options import EasyOcrOptions, PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat

opts = PdfPipelineOptions()
opts.do_ocr = True
opts.ocr_options = EasyOcrOptions(lang=["en", "ar", "fr"])   # ar + fr is illegal in EasyOCR
conv = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)})
conv.convert("any.pdf")   # -> ValueError raised from inside the pipeline, per document
```

**Root cause.** EasyOCR groups scripts; Arabic-family languages (`ar/fa/ur/ug`) can only be
combined with English, never with Latin languages. Docling passes the list straight through
to `easyocr.Reader(...)`, which validates only at construction time — and construction is
lazy/per-conversion, so the failure surfaces once per document instead of once at setup.

**Proposed fix.** Validate `EasyOcrOptions.lang` when the options are constructed (or when the
converter is built), and raise a clear, early error naming the incompatible pair — or expose a
helper that splits an incompatible set into compatible reader groups. Even a docstring note on
`EasyOcrOptions.lang` documenting the EasyOCR script-grouping constraint would help.

---

## 2. No "skip rendering/OCR when the page already has a text layer" fast path

**Severity:** medium effort, high value — the meaty one.

**Symptom.** A digital PDF (selectable text layer on every page) is processed through the full
image pipeline: each page is rendered to a bitmap and run through layout/table/OCR models,
even though the text is already directly available.

**Measured impact (19-page Arabic report, this project).**

| Path | Time | Arabic chars extracted | Result |
|------|------|------------------------|--------|
| docling full pipeline (`do_ocr=True`) | ~29 s | 177 | partial, `std::bad_alloc` on some pages |
| direct text-layer read (`pypdfium2`) | ~0.02 s | 1264 | complete, no crash |

The direct read was **~1400× faster and extracted 7× more of the actual Arabic text.**

**Reproduction.** Convert any digital PDF and compare `pypdfium2` `get_text_range()` output
against docling's `export_to_markdown()` — for text-layer PDFs the native text is both faster
and (for RTL/Arabic especially) more faithful.

**Root cause.** Docling always drives its image-based pipeline for PDFs; there is no per-page
short circuit that detects an existing text layer and reads it directly instead of rendering.

**Proposed fix.** A per-page (or per-document) text-layer detection that, when present, extracts
text directly and skips rendering/layout/OCR for that page. Pages that are genuinely image-only
still go through the full pipeline. This is exactly the routing we had to implement outside
docling to make the module usable on low-memory hardware.

---

## 3. Eager page rendering exhausts memory on large documents (`std::bad_alloc`)

**Severity:** higher effort — real robustness feature.

**Symptom.** On a machine with limited RAM, converting a large PDF (~28 pages, dense Arabic +
embedded images) aborts individual pages with:

```
Stage preprocess failed for run 1, pages [12]: std::bad_alloc
Stage preprocess failed for run 1, pages [14..28]: std::bad_alloc
```

Notably this happens in the **preprocess** stage (page-image rendering for the layout/table
models) even with `do_ocr=False` — so it is not OCR-specific. The conversion returns
`PARTIAL_SUCCESS` with the failed pages' content silently missing.

**Root cause (as understood).** Page bitmaps are large (a scaled A4 is multiple megapixels) and
the pipeline appears to render/hold more than one page's worth at once. On constrained memory
this overflows. The failure is per-page and swallowed into a partial result, so downstream
consumers lose content without a hard error.

**Proposed fix.**
- A bounded-memory / streaming mode that renders, processes, and **releases** one page at a
  time so peak memory is ~one page, independent of document length.
- A configurable render scale/DPI cap (a lower default for OCR is usually sufficient).
- Surface per-page preprocess failures more prominently than a quiet `PARTIAL_SUCCESS` (e.g.
  a structured list of failed pages on the result), so callers can react.

---

## Cross-cutting observation

All three point the same way: **docling does its heaviest work unconditionally**, which is fine
on a big machine but brittle on limited RAM and wasteful for the common case (digital PDFs).
A "do the cheap thing when you can, do the heavy thing only when you must, and bound its
memory" posture would make it robust across a much wider range of inputs and hardware.
