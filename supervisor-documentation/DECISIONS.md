# Architecture Decision Record: EY CX Studio

This file records major engineering decisions and their rationale. New decisions should be appended with date, status, context, decision, and consequences.

## ADR-001: Use FastAPI for the Backend

- Date: Existing decision
- Status: Accepted
- Context: The platform needs typed APIs, async request handling, file uploads, background-friendly services, and Pydantic validation.
- Decision: Use FastAPI with Pydantic schemas and route modules grouped by feature.
- Consequences: The backend has strong request validation and clear route boundaries, but async database and service patterns must be followed carefully.

## ADR-002: Use React, TypeScript, and Vite for the Frontend

- Date: Existing decision
- Status: Accepted
- Context: The frontend needs a rich single-page application with module dashboards, reports, chats, and exports.
- Decision: Use React 19, TypeScript, Vite, and Tailwind CSS v4.
- Consequences: Development is fast and type-aware; frontend behavior must be verified through type checks, tests, and production builds.

## ADR-003: Keep Projects as a Layer Over Modules

- Date: Existing decision
- Status: Accepted
- Context: Consultants should be able to run modules independently or inside a client engagement.
- Decision: Make projects an organizing layer for module artifacts rather than a required dependency.
- Consequences: Modules remain reusable, while projects provide engagement-level traceability.

## ADR-004: Route All LLM Calls Through One Gateway

- Date: Existing decision
- Status: Accepted
- Context: LLM usage needs consistent retry behavior, cost tracking, and optional tracing.
- Decision: All model calls go through the shared LLM gateway.
- Consequences: Usage is recorded in `llm_calls`, retries are consistent, and features should not create direct provider HTTP calls.

## ADR-005: Compute Numbers in Python, Not With LLMs

- Date: Existing decision
- Status: Accepted
- Context: Reports need reproducible metrics and trustworthy figures.
- Decision: Compute statistics in backend logic and pass them into prompts for narrative explanation.
- Consequences: Numeric outputs are more reliable; prompt work focuses on interpretation rather than calculation.

## ADR-006: Use PostgreSQL Plus Storage Abstraction

- Date: Existing decision
- Status: Accepted
- Context: The app stores relational records as well as large extracted documents, report files, and vector indexes.
- Decision: Store structured records in PostgreSQL and large artifacts through a storage service.
- Consequences: The database remains suited to transactional state, and storage can switch between local disk and production object storage.

## ADR-007: Use Numbered SQL Migrations as Schema Source of Truth

- Date: Existing decision
- Status: Accepted
- Context: The project needs explicit, reviewable database changes.
- Decision: Database schema is defined in `backend/migrations/`; SQLAlchemy models mirror it.
- Consequences: ORM changes require matching migrations. `seed.py` applies migrations and reference data.

## ADR-008: Use Jobs and Polling for Long-Running Work

- Date: Existing decision
- Status: Accepted
- Context: Scraping and issue-log generation can exceed request timeouts.
- Decision: Create persistent job records, run work in background tasks, and let the frontend poll status.
- Consequences: Users can recover from tab closes and long operations avoid proxy timeout limits.

## ADR-009: Store Access Tokens in Memory

- Date: Existing decision
- Status: Accepted
- Context: The app handles sensitive client analysis and should reduce session persistence risk.
- Decision: Store short-lived access tokens in browser memory and rotating refresh tokens in `HttpOnly` cookies.
- Consequences: Access tokens are harder to steal from browser storage; refresh behavior must be handled carefully by the API client.

## ADR-010: Use Scoped Respondent Tokens for Client Assessment Links

- Date: Existing decision
- Status: Accepted
- Context: Clients need to answer assessments without consultant accounts.
- Decision: Use passwordless respondent tokens scoped to exactly one assessment.
- Consequences: Client access remains narrow and revocable; no route should accept bare assessment ids for respondent actions.

## ADR-011: Use Local RAG With Fallback Instead of a Vector Database

- Date: Existing decision
- Status: Accepted
- Context: Expected retrieval volumes are manageable and a separate vector database increases deployment complexity.
- Decision: Store chunks and vectors through the storage layer and use numpy similarity search, with lexical fallback.
- Consequences: Deployment is simpler; very large corpora may eventually require a dedicated vector database.

## ADR-012: Serve Built Frontend From FastAPI in Production

- Date: Existing decision
- Status: Accepted
- Context: Same-origin cookies simplify secure refresh-token behavior.
- Decision: The Docker image builds the frontend and serves it from the FastAPI process when static files are present.
- Consequences: Production deployment can use one container and same-origin cookies; local development still uses Vite.
