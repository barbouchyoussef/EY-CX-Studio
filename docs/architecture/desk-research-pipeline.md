# Desk Research — Document Parsing & Synthesis Pipeline

Code: `backend/app/services/desk_research/`. UI: `frontend/src/features/desk-research/hub.tsx`.

A consultant creates a **session**, uploads documents (PDF / DOCX / PPTX / XLSX / images), and gets
(1) a RAG **chat** over the documents and (2) an **executive synthesis report**. This doc covers how
raw files become structured, searchable content and then a report.

## 1. Ingestion & orchestration

Entry point: `pipeline.process_file(session_id, filename, content)` (called per upload, files run
concurrently via `process_files`). It **never raises** — any failure at any stage returns a
`ProcessedDocument` with `status="failed"` and a readable error, so one bad file can't sink a batch.

```
upload bytes → repair mojibake filename → validate extension → save original
             → ROUTE by type → extract → save ProcessedDocument JSON
```

Supported formats (`converter.ALLOWED_EXTENSIONS`): `.pdf`; `.docx/.doc`, `.pptx/.ppt`,
`.xlsx/.xls`; images `.png .jpg .jpeg .tiff .tif .bmp .webp`. The engine is **IBM Docling** (layout
+ table models), built once and cached (`@lru_cache`), run in `asyncio.to_thread`.

## 2. The routing decision — digital vs. everything else

Before invoking Docling, `converter.has_text_layer(pdf)` samples the first ≤6 pages via `pypdfium2`
and returns `True` if they carry ≥120 text characters.

- **Path A — digital PDF (fast):** `extractor.extract_pdf_native` reads the text layer directly with
  pypdfium2. Docling's page-image rendering is the memory hog (the `std::bad_alloc` on heavy Arabic
  reports); a text-layer PDF needs none of it — fast, crash-free, and better Arabic fidelity.
- **Path B — Docling:** scanned PDFs, images, and all Office formats go through Docling's full
  pipeline (OCR + TableFormer).

> This is a per-document boolean, but it is **not** a correctness risk for mixed PDFs (see §4) — both
> paths OCR their uncovered pages.

## 3. OCR (multilingual constraint)

OCR is **EasyOCR**. A hard EasyOCR rule: **Arabic cannot be combined with Latin scripts** — asking
for `["en","ar","fr"]` throws *inside* `convert()`, once per document (documented in
[docling-issues.md](docling-issues.md)). `converter._resolve_ocr_langs()` therefore defaults to **Arabic + English**
(`DESK_OCR_LANGS`, overridable) and strips any illegal mix. Rationale: scanned Arabic docs are the
ones that truly need OCR; French/English digital PDFs get text from the native pass regardless.

## 4. Mixed & vector PDFs — per-page OCR fallback

Two hard cases a naive "digital vs scanned" split gets wrong, both handled:

- **Mixed PDF** (text pages + scanned pages): the native path reads text pages, then
  `_run_pdf_page_ocr_fallback` OCRs the pages that produced no text — one page at a time
  (`render scale 1.5`, capped `_MAX_OCR_FALLBACK_PAGES = 25`, memory-flat). Text pages stay fast;
  scanned pages inside the same file are still read.
- **Vector PDF** (dashboard exported as vector shapes — no text layer *and* no image objects, e.g.
  the Web Analytics export): Docling labels each page a "picture" and extracts nothing (markdown of
  46 chars of `<!-- image -->`). The fix: `_run_pdf_page_ocr_fallback` counts a page "covered" only
  if it has real **text or a table** — *not* merely an image caption — so these image-only pages get
  rendered and OCR'd, recovering their data.

## 5. Figures / images → vision captioning

Images (from either path) become captioned blocks via `_build_image_blocks`. Cost & noise controls,
in order:

1. **Decorative pre-filter** (`_is_decorative`): drops tiny icons (`< 100px` both dims), thin strips
   (`min dim < 40px`), and banners (aspect ratio `≥ 7`).
2. **Boilerplate filter:** an image whose content-hash appears on **≥ 3 pages** is a
   header/footer/logo/watermark → dropped (this is what removes the brand logo that otherwise gets
   transcribed once per page).
3. **Content-hash dedup:** an identical image is captioned once, shared across its blocks.
4. **Bounded-concurrency captioning** (4 workers) of the survivors.

Captioner: `gemini_vlm.MultiProviderVLMClient` — a 3-tier failover: **Gemini** (key + model
rotation) → **OpenRouter** → **local EasyOCR**. Its prompt asks it to *transcribe chart/table data
precisely* (titles, labels, every number) and to return the sentinel **`DECORATIVE`** only when
unmistakably a logo/banner (with "when in doubt, describe it" — so a real chart is never dropped).
A `DECORATIVE` result is discarded.

## 6. Structured output & rescue passes

Both paths converge on `ProcessedDocument`: a flat list of `DocumentBlock`s (headings, paragraphs,
tables, images) **plus a full-document markdown export**. Tables export to row-dicts (guarded
per-table); `_compact_table_markdown` trims tables to their populated columns.

The Docling path (`extractor.extract`) has rescue passes when Docling comes up thin
(`len(markdown) < 500`): append pypdfium native text, then `_run_pdf_page_ocr_fallback` OCR, and for
**PPTX** a direct `python-pptx` slide re-extraction.

## 7. Encoding repair (mojibake)

All extracted text passes through `repair_encoding`, which fixes
UTF-8-decoded-as-CP1252/Latin-1 mojibake per-run (so mixed content is safe): it recovers Arabic
(`Ø§ÙØ¬ÙØ¯Ø©` → `الجودة`), punctuation (`Acmeâ€™s` → `Acme's`) and CP1252-mangled symbols
(`â‰¤` → `≤`, `2022â€"2025` → `2022–2025`). It runs at generation **and on read**
(`session_manager` heals older stored reports on load).

## 8. RAG index & chat

Extracted markdown + blocks are folded into a per-session index (`rag_index.py`) — the executive
report is itself indexed (`REPORT_SOURCE_ID`) so the chat can retrieve it. Chat answers ground every
claim in retrieved excerpts and cite `[filename, p<page>]` (`CHAT_SYSTEM_PROMPT` in `synthesizer.py`).

## 9. The synthesis report

`synthesizer.py` produces the executive report. Small sessions use a single LLM pass; large ones use
**map-reduce** (`_SINGLE_PASS_CHAR_BUDGET = 120k`): a `MAP_SYSTEM_PROMPT` extracts facts per document
chunk (deliberately extractive — carry every number forward), then a reduce step synthesizes.

`REPORT_SYSTEM_PROMPT` enforces the structure and voice:

- **Entire report in clear, professional English** regardless of source language (Arabic/French
  translated; proper nouns, figures, dates kept verbatim).
- **Part 1 — Executive Synthesis:** Executive Summary · The Document Set at a Glance (table) · How
  the Documents Relate (corroboration / contradiction / recurring themes) · Key Findings Across the
  Set · Risks & Data Gaps · Recommendations.
- **Part 2 — Document Deep-Dives:** one `### English-title` section per document (What it is · What
  it says + data table · Standout findings · Connections).
- Every finding states the fact **and** its "so what"; strict data fidelity; no filler.

Rendered on the frontend by a custom `MarkdownRenderer` (regex-based heading handling for all levels,
styled tables, RTL-aware via `dir="auto"`).

## Known limitations

- OCR/VLM on **dense Arabic charts** is imperfect — headline figures come through, tiny axis labels
  can be misread.
- The `has_text_layer` sample and the 25-page OCR cap are heuristics tuned for memory safety; both
  are configurable.
- Sessions live in the **file store** (`desk_research_data/`) — a storage-hardening target.
