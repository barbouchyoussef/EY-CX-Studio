# Technical Specification: EY CX Studio

## 1. Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4 |
| Backend | Python 3.12, FastAPI, Pydantic |
| Database | PostgreSQL with numbered SQL migrations |
| ORM | SQLAlchemy 2 |
| Tests | Pytest, Vitest, React Testing Library |
| Document processing | Docling, pypdfium2, EasyOCR, python-pptx |
| Retrieval | Local embeddings with `sentence-transformers`, numpy vector search, lexical fallback |
| LLM providers | Mistral primary, optional Moonshot, Gemini, OpenRouter |
| Observability | `llm_calls` table and optional Langfuse tracing |
| Deployment | Dockerfile builds frontend and backend into one image |

## 2. Repository Structure

```text
backend/
  app/
    api/routes/        FastAPI route modules
    services/          Feature services and shared service layers
    repositories/      Database access
    db/models/         SQLAlchemy mappings
    schemas/           Pydantic request and response schemas
  migrations/          Ordered SQL migrations
  tests/               Backend test suite
frontend/
  src/
    features/          Frontend modules by feature
    components/ui/     Shared UI components
    lib/               API client, shared utilities, copy, brand constants
docs/
  architecture/        Existing detailed architecture notes
```

## 3. Backend Requirements

- All API routes are mounted under `/api/v1`.
- Routers live in `backend/app/api/routes/`.
- Routes must delegate business logic to services.
- Services must use repositories or unit-of-work boundaries for database access.
- Database schema changes require a numbered SQL migration.
- LLM calls must go through the shared gateway so retries and usage logging are applied.
- Long-running tasks must run as jobs with persistent status and frontend polling.
- Runtime files must use the storage service rather than direct path access.

## 4. Frontend Requirements

- Feature code lives under `frontend/src/features/<feature>/`.
- Each feature exposes public imports through its `index.ts`.
- Shared reusable components belong in `frontend/src/components/ui/`.
- API calls should use the shared API helpers.
- Authentication state must not persist access tokens in `localStorage`.
- Brand colors must remain synchronized between CSS tokens and TypeScript constants.
- User-facing module copy should support English and French where applicable.

## 5. Authentication and Authorization

- Access is invite-only.
- Access tokens are short-lived and stored in browser memory.
- Refresh tokens are stored in an `HttpOnly` cookie and rotate on refresh.
- Admin routes require admin dependency enforcement.
- Ownership and project membership checks are centralized through the access service.
- Respondent tokens are hashed, scoped to one assessment, expirable, and revocable.

## 6. Data Persistence

- PostgreSQL stores identity, projects, assessments, reports metadata, jobs, reference data, and observability.
- Object or disk storage stores large runtime artifacts such as desk research content, RAG indexes, and social report files.
- The storage backend is selected by `STORAGE_BACKEND`.
- Development defaults to disk storage.

## 7. External Integrations

| Integration | Purpose | Failure Mode |
|---|---|---|
| Mistral | Main LLM generation | Generative features fail gracefully. |
| Moonshot | Optional chat provider | Falls back when not configured. |
| Gemini | Text failover and image captioning | Image descriptions may be unavailable. |
| OpenRouter | Vision fallback | No VLM fallback if unset. |
| LangSearch | Benchmark evidence search | Benchmark section may be omitted. |
| Apify | Social scraping | Social collection unavailable. |
| Bright Data | Facebook page/comment scraping | Facebook page scraping skipped. |
| SMTP | Invites and password reset | Tokens must be copied manually where supported. |
| Langfuse | Prompt/response tracing | Local `llm_calls` remains available. |

## 8. Configuration

Backend environment variables are documented in `backend/.env.example`. Required local setup:

- `DATABASE_URL`
- `JWT_SECRET` outside development
- LLM and provider keys for generative or scraping features

Frontend configuration:

- `VITE_API_BASE_URL`, defaulting to the local API.

## 9. Quality Requirements

- Run backend tests with `python -m pytest` from `backend/`.
- Run frontend verification with `npm run verify` from `frontend/`.
- Run frontend linting with `npm run lint`.
- Any release candidate should pass both backend and frontend checks.
- New features should include focused tests when they affect shared behavior, security, scoring, extraction, or long-running jobs.

## 10. Constraints

- Network-dependent features require provider credentials.
- Large local model downloads can slow first use.
- Docker image size is affected by document processing and ML dependencies.
- The schema is migration-owned; ORM changes alone are not sufficient.
- The current frontend uses hand-rolled path routing rather than a router library.
