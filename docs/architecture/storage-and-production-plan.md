# Data Storage — Current State & Production Plan

Where every module's data lives, and the plan that got it there.

> **Status.** This was written as a roadmap and most of it has since been carried out. The
> storage abstraction exists (`backend/app/services/storage.py`), selecting a backend from
> `STORAGE_BACKEND`: local disk in development, Supabase Storage in production. Social listening
> and desk research write through it rather than to the filesystem, so the directory names below
> are key prefixes now. The consolidation module described in section 5 was built and shipped as
> the **issue log** (`backend/app/services/issue_log/`, `frontend/src/features/issue-log/`).
>
> The storage map in section 1 is still accurate and is the reason to keep this document. Section
> 6 is kept as a record of the sequencing that was followed, not as outstanding work.

## 1. Current storage map (the truth)

### Postgres (34 tables) — the structured core
- **Auth:** `users`, `invites`, `refresh_tokens`, `password_reset_tokens`.
- **Projects & sharing:** `projects`, `project_members`, `project_steps`, `project_artifacts`,
  `analysis_shares`.
- **Maturity Assessment — fully in Postgres:** `assessments`, `assessment_answers`,
  `assessment_scores`, `assessment_axis_memory`, `assessment_insights`, `assessment_recipients`,
  `assessment_website_audits`, `recommendation_outputs`, `assessment_idempotency`.
- **Interview Guides — fully in Postgres:** `interview_guides` (payload + insights as JSONB).
- **Companies & reference data:** `companies`, `sectors`, `company_sizes`, `regions`, `axes`,
  `capabilities`, `maturity_levels`, rubrics/templates, detections.
- **Social Listening:** `scraping_jobs` — **includes `request` and `result` as JSONB** (the report
  result already lands in Postgres).

### File stores (on local disk) — the production risk
| Path | Size | Contents |
|---|---|---|
| `desk_research_data/<session>/` | ~17 MB | `originals/` (uploaded blobs), `images/` (extracted image blobs), `processed/` (ProcessedDocument JSON), `session.json` (metadata + report markdown), RAG index |
| `scraped_data/*.json` | ~1.5 MB | Social report JSON — **largely redundant** with `scraping_jobs.result` |
| `projects_data/` | ~1 KB | Legacy JSON project store — **dead**, superseded by Postgres. Delete. |

### Summary by module
- **Assessment, Interviews → 100% Postgres.** Production-ready.
- **Social Listening → data already in `scraping_jobs.result` (JSONB)**, but the read/list path still
  reads `scraped_data/` files. Small gap.
- **Desk Research → 100% file-based.** The real work.
- No object storage anywhere; no pgvector; RAG index is disk/in-process.

## 2. Why it isn't production-ready

1. **Ephemeral filesystem.** Most free/PaaS hosts (Render, Railway, Fly, Heroku) wipe the disk on
   every redeploy/restart. `desk_research_data/` and `scraped_data/` **would be lost** — uploaded
   documents, extracted images, reports, RAG index, all gone.
2. **No horizontal scaling.** File stores are tied to one instance's disk; a second instance can't
   see them.
3. **No backups.** Managed Postgres is backed up; loose files are not.
4. **Two-worlds complexity.** Ownership/sharing (`owned` flags, `access.py`) has to special-case
   files vs. rows.
5. **Blocks the final module** (see §5): a consolidator can't reliably read module outputs that live
   as owner-scoped files on an ephemeral disk.

## 3. Target architecture

**Principle: structured/queryable data → Postgres (JSONB + pgvector); large binary blobs → object
storage (S3-compatible). Never put multi-MB PDFs/images in Postgres.**

| Data | Home |
|---|---|
| All metadata, extracted text, `DocumentBlock`s, classifications, report markdown, report JSON | **Postgres (JSONB)** |
| Uploaded original documents, extracted page/figure images | **Object storage bucket** (Postgres stores the object key) |
| RAG embeddings | **pgvector** (Postgres extension) |

Object storage options for a free/cheap deploy: **Cloudflare R2** (free tier, no egress) or
**Supabase Storage** (if using Supabase Postgres). Abstract it behind a tiny `storage` interface —
local disk in dev, S3 in prod — so no path is hard-coded.

### Per-module target
- **Assessment / Interviews:** already Postgres — no change.
- **Social Listening:** make `scraping_jobs.result` the single source of truth; serve the dashboard
  list + a report from the row (its `ref_id` becomes the job/report id). Retire `scraped_data/`.
  Cheap — the data is already there.
- **Desk Research:** new tables `desk_sessions` + `desk_documents` (JSONB for blocks/markdown/
  classifications); originals + images → object storage (keys in PG); embeddings → pgvector. The
  RAG "shared engine" reads from pgvector instead of disk.

## 4. Migration steps (sequenced)

1. **Storage abstraction** — a `storage` module with `put/get/url/delete`, backed by local disk (dev)
   or S3/R2 (prod), selected by env. Document `STORAGE_BACKEND`, bucket, and creds in `.env.example`.
2. **Migrations** — numbered SQL for `desk_sessions`, `desk_documents`; `CREATE EXTENSION vector`;
   an embeddings table. (Social needs none — reuse `scraping_jobs`.)
3. **Rewrite the two services** — desk `session_manager` and social `list_reports`/report-serving to
   read/write Postgres + object storage instead of disk.
4. **One-time data migration** — move existing `desk_research_data/` + `scraped_data/` into PG +
   bucket (or accept a dev-data reset for the temporary test deploy).
5. **Cleanup** — delete `projects_data/`; retire `scraped_data/`; add `.gitignore` for the dev-local
   store dirs.

## 5. The final module — consolidation → full Excel (design it into the storage now)

The final module takes inputs from **all** modules for a project and outputs a full Excel workbook.
The storage plan is its prerequisite:

- **Discovery via `project_artifacts`.** A project already links every module output as an artifact
  (`kind ∈ {assessment, interview_guide, social_report, desk_session}` + `ref_id`). The consolidator
  iterates a project's artifacts and resolves each to its data. **This only works cleanly if every
  output is queryable in Postgres** — which is exactly what §3 delivers.
- **A common "Finding" abstraction.** Define one normalized shape every module maps to:
  `{ source_kind, source_ref, title, category/theme, severity, metric, evidence }`.
  - Assessment → per-axis maturity gaps + recommendations.
  - Interview → persisted insights.
  - Social → complaint categories, friction points, negative-theme momentum.
  - Desk → risks & data gaps, key findings.
  Persist as `issue_log_entries (project_id, source_kind, source_ref, category, severity, description,
  evidence, created_at)` — generated from the artifacts, editable by the consultant.
- **Excel output.** Backend generates a workbook (openpyxl) with one sheet per module + a
  consolidated **Issue Log** sheet (ranked by severity), pulling entirely from Postgres. Downloadable
  from the project. (The frontend already uses ExcelJS for the social export — the pattern exists.)

> Net: the storage move was step 1 of the final module. Consolidation across the four modules is a
> read-and-aggregate problem once everything goes through one storage layer, and an impossible
> file-crawl otherwise. This is what the issue log was built on.

## 6. Sequencing (followed, in this order)

1. ~~Provision managed Postgres + an object store.~~ Done: Supabase.
2. ~~Add the `storage` abstraction + config.~~ Done: `app/services/storage.py`.
3. ~~Migrate Desk Research.~~ Done, through the same abstraction.
4. ~~Flip Social Listening to read from `scraping_jobs.result`.~~ Done.
5. ~~Delete legacy `projects_data/`.~~ Done: projects are in Postgres.
6. ~~Build the consolidation module.~~ Done: the issue log.

pgvector was not adopted. Retrieval stores its vectors as numpy arrays through the same storage
abstraction, which was enough at the volumes involved and one fewer service to run. See
[retrieval-and-chatbots.md](retrieval-and-chatbots.md).

Assessments and interviews need nothing — they're already production-shaped.
