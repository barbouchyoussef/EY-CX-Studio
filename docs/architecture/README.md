# EY CX Studio — Architecture Overview

> Living technical reference for the current platform. One file per major pipeline lives in this
> folder, alongside notes on decisions that are not visible in the code. File paths are real and
> point at the code.
>
> For a walkthrough of a feature end to end, start with [DEEPDIVE.md](../../DEEPDIVE.md); these
> documents go deeper on individual pipelines and the reasoning behind them.

## What the platform is

**EY CX Studio** is an internal, multi-user consulting workspace that brings five AI-assisted CX
analysis modules under one project-centric roof. A consultant logs in, works inside a **project**
(which owns the results and its members), runs any of the modules, and shares outputs with
colleagues — or sends a passwordless link to an external client.

The five modules. The first four share the **same dashboard pattern** (land on a table of saved
work → open / share / delete / import-to-project → "New"); the issue log consumes their output
rather than producing its own kind of analysis:

| Module | What it does | Pipeline doc |
|---|---|---|
| **Maturity Assessment** | Conversational CX-maturity diagnostic scored across Manage / Analyze / Improve; can be self-run or sent to a client as a passwordless link | [maturity-assessment-and-interviews.md](maturity-assessment-and-interviews.md) |
| **Interview Guide** | Generates a tailored stakeholder interview guide (from an assessment or from scratch); persists AI insights | [interview-guides.md](interview-guides.md) |
| **Social Listening** | Scrapes public reviews/posts, AI-classifies sentiment/themes/complaints (+ ad filtering), builds an analytics report | [social-listening-pipeline.md](social-listening-pipeline.md), [social-listening-engineering.md](social-listening-engineering.md) |
| **Desk Research** | Multi-format document parsing (PDF/Office/images, OCR, vision) → RAG chat + an executive synthesis report | [desk-research-pipeline.md](desk-research-pipeline.md) |
| **Issue Log** | Consolidates the findings of the other four into one prioritised issue register, surfacing where sources disagree, and exports it to Excel | [DEEPDIVE.md](../../DEEPDIVE.md) |

Cross-cutting systems:
- Auth, projects, per-analysis sharing: [auth-projects-and-sharing.md](auth-projects-and-sharing.md)
- How each module grounds its chatbot, and why there is no vector database: [retrieval-and-chatbots.md](retrieval-and-chatbots.md)
- LLM call tracing and cost: [observability.md](observability.md)
- Where each module's data lives: [storage-and-production-plan.md](storage-and-production-plan.md)
- The ordered checklist for building a sixth module, and the places that already know how
  many there are: [adding-a-module.md](adding-a-module.md)
- Capability boundaries the assessment must keep routing correctly, checked by hand:
  [assessment-routing-baseline.md](assessment-routing-baseline.md)
- Docling limitations this project works around, with measurements:
  [docling-issues.md](docling-issues.md)

## Tech stack

- **Backend:** FastAPI (async), SQLAlchemy 2.0 + asyncpg, PostgreSQL. LLMs via Mistral / Gemini /
  OpenRouter gateways. Docling + EasyOCR + a vision model for document parsing.
- **Frontend:** React 19 + Vite + TypeScript, Tailwind. Hand-rolled routing in `App.tsx`
  (`pathname.startsWith`), no react-router.
- **Auth:** short-lived JWT access token (in memory) + rotating refresh token in an HttpOnly cookie.
- **Migrations:** hand-written numbered SQL in `backend/migrations/`, applied idempotently by
  `backend/seed.py`. **No Alembic.**

## Repo layout (the parts that matter)

```
backend/
  app/
    api/routes/         # FastAPI routers (auth, assessments, scraping, desk_research, projects, respondent, ...)
    services/
      assessment/       # maturity assessment + interview guides + client links
      scraping/         # social listening: scraping, classification, analytics, report
      desk_research/    # document parsing pipeline + synthesizer
      auth/             # security (JWT/bcrypt), access.py (authorization brain)
      projects/         # project service (members, artifacts, shares)
    db/models/          # SQLAlchemy models
    schemas/            # Pydantic request/response models
  migrations/           # numbered SQL, applied by seed.py
frontend/
  src/features/         # one folder per module + projects + auth, each behind an index.ts
                        #   assessment/ (with report/ and client/), interview/, social/,
                        #   desk-research/, issue-log/, projects/, admin/, auth/
  src/components/ui/    # shared components only (chat, header, share, nav, primitives)
  src/lib/              # api.ts (authFetch), projectsApi.ts, respondentApi.ts, shared hooks
  src/context/          # AuthContext, ActiveProjectContext
docs/architecture/      # this folder
```

## The two persistence worlds (important)

- **Postgres:** users, invites, projects (members / steps / artifacts), analysis shares,
  assessments, interview guides. Ownership (`owner_id`) is enforced.
- **Object storage:** social reports (`scraped_data/*.json`) and desk-research sessions
  (`desk_research_data/`), each carrying an `owner_id`. These no longer touch the filesystem
  directly: everything goes through `app/services/storage.py`, which selects a backend from
  `STORAGE_BACKEND` — local disk in development, Supabase Storage in production. The names above
  are key prefixes now, not directories.

## Authorization model (one sentence)

Every list/read/mutate routes through `app/services/auth/access.py` — a caller sees an analysis if
they **own** it, it's **shared** with them (`analysis_shares`), or it's **attached to a project**
they're a member of. `owned` vs shared is surfaced on every dashboard as a "Shared with you" tag.

## Key end-to-end flows

1. **Consultant runs a module in a project** → result auto-attaches to the project as an *artifact*
   (`kind` + `ref_id`) and advances the pipeline step.
2. **Passwordless client assessment** → consultant mints a link (`/a/<token>`); the client fills a
   short profile then the assessment; the completed report lands on the consultant's dashboard.
   See the assessment doc for the respondent auth path.
3. **Sharing** → a consultant shares an analysis (by email) from its dashboard row; the recipient
   sees it tagged "Shared with you" and can open (but not delete/re-share) it.

## Conventions

- New DB changes = a new numbered SQL file in `backend/migrations/`, applied by `seed.py`.
- New routes = an `APIRouter(prefix=...)` registered in `app/api/router.py`, all under `/api/v1`.
- Document every new env var in `backend/.env.example`.
- Frontend API calls go through `authFetch`/`authFetchUrl` (consultant) or `respondentApi` (client).
