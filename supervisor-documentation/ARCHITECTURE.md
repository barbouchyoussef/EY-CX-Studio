# Architecture: EY CX Studio

## 1. System Overview

EY CX Studio is a full-stack web application with a React/Vite frontend and a FastAPI backend. The backend exposes a versioned API under `/api/v1`, persists relational data in PostgreSQL, stores large runtime artifacts through a storage abstraction, and integrates with LLM and data-provider services for generation, retrieval, scraping, and analysis.

```text
Browser
  |
  | React SPA
  v
FastAPI API (/api/v1)
  |
  +-- Auth and access control
  +-- Feature services
  +-- LLM gateway
  +-- RAG engine
  +-- Storage service
  |
  +-- PostgreSQL
  +-- Disk/Supabase object storage
  +-- External providers
```

## 2. Major Components

| Component | Responsibility |
|---|---|
| React SPA | User interface for consultants, admins, and respondent flow. |
| FastAPI routes | HTTP boundary, validation, dependency resolution. |
| Services | Business logic for each feature module. |
| Repositories | Database reads and writes. |
| Unit of work | Transaction boundaries for coordinated writes. |
| LLM gateway | Shared retries, provider calls, and usage logging. |
| RAG engine | Chunking, embedding, retrieval, and cited answers. |
| Storage service | Disk or object storage access behind one API. |
| Background jobs | Long-running scraping and issue-log execution. |

## 3. Frontend Architecture

- `frontend/src/App.tsx` owns route selection using path checks.
- `frontend/src/features/` contains one folder per product module.
- `frontend/src/components/ui/` contains shared UI components.
- `frontend/src/lib/api.ts` handles authenticated requests and refresh-on-401 behavior.
- `frontend/src/context/AuthContext.tsx` manages login state.
- `frontend/src/context/ActiveProjectContext.tsx` tracks the active project.

Feature folders encapsulate their own views, copy, types, exports, and local helpers. Shared imports should come from feature `index.ts` files instead of deep module paths.

## 4. Backend Architecture

- `backend/app/main.py` creates the FastAPI app, CORS policy, lifespan behavior, and static frontend serving in production.
- `backend/app/api/router.py` registers all feature routers.
- `backend/app/api/routes/` contains route modules.
- `backend/app/services/` contains feature services and shared service infrastructure.
- `backend/app/repositories/` contains database-access classes.
- `backend/app/schemas/` contains Pydantic schemas.
- `backend/app/db/models/` mirrors the migration-owned database schema.

Routes should remain thin. Services coordinate validation, scoring, provider calls, persistence, and report assembly.

## 5. Data Flow by Module

### Maturity Assessment

```text
Consultant/respondent answer
  -> API route
  -> conversation service
  -> intent routing and coverage detection
  -> scoring and memory update
  -> next question or final report
  -> PostgreSQL
```

### Desk Research

```text
Uploaded files
  -> extraction pipeline
  -> native extraction / Docling / OCR / VLM captioning
  -> report synthesis
  -> RAG indexing
  -> storage and API response
```

### Social Listening

```text
Run request
  -> job row
  -> background scraping
  -> item classification
  -> Python analytics
  -> generated narrative
  -> job result and frontend polling
```

### Issue Log

```text
Selected analyses
  -> access check
  -> finding collection
  -> source chunking
  -> issue generation and normalization
  -> conflict correlation
  -> recommendations and export
```

## 6. API Surface

All endpoints are under `/api/v1`.

| Prefix | Area |
|---|---|
| `/auth` | Login, refresh, invites, password reset. |
| `/assessments` | Maturity assessments and interview guide flows. |
| `/respondent` | Passwordless client assessment flow. |
| `/reference` | Reference data. |
| `/consultations` | Consultation requests. |
| `/scraping` | Social listening. |
| `/desk-research` | Document analysis and report chat. |
| `/projects` | Projects, members, pipeline, artifacts. |
| `/shares` | Analysis sharing. |
| `/issue-log` | Issue log generation and export. |
| `/admin/*` | Admin reference, capability, and analytics workflows. |

## 7. Security Architecture

- Invite-only account creation.
- Access token in browser memory only.
- Rotating refresh token in `HttpOnly` cookie.
- Central access checks for ownership, sharing, and project membership.
- Admin dependency required for admin endpoints.
- Respondent flow uses scoped tokens rather than assessment ids alone.
- Sensitive runtime configuration is loaded from environment variables.

## 8. Design Decisions

- Use one LLM gateway for observability, retries, and cost tracking.
- Compute metrics in Python and ask models only for prose.
- Use PostgreSQL for structured records and storage service for large artifacts.
- Use jobs and polling for operations that may exceed normal HTTP request time.
- Keep projects as a layer over modules, not a required dependency for modules.
- Use migrations as the source of truth for the database schema.

## 9. Deployment Architecture

The Dockerfile builds the frontend and backend into one container. In production, FastAPI serves both the API and built frontend assets from the same process. This supports same-origin cookie behavior for refresh tokens.

Metabase is defined separately in `docker-compose.yml` for analytics dashboards and is not the main application database.
