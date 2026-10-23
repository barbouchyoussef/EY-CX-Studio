# API Specification: EY CX Studio

## 1. Overview

The backend exposes a REST-style FastAPI API under `/api/v1`. API routes are grouped by feature in `backend/app/api/routes/` and registered through `backend/app/api/router.py`.

## 2. Base URL

| Environment | Base URL |
|---|---|
| Local backend | `http://127.0.0.1:8000/api/v1` |
| Local frontend proxy/config | Controlled by `VITE_API_BASE_URL` |
| Production | Same origin as deployed frontend, under `/api/v1` |

## 3. Authentication

- Consultant and admin routes require authentication.
- Access tokens are short-lived and sent as bearer tokens.
- Refresh tokens are stored in an `HttpOnly` cookie.
- Respondent routes use an assessment-scoped respondent token.

## 4. API Areas

| Prefix | Purpose |
|---|---|
| `/health` | API health checks. |
| `/auth` | Login, refresh, invitations, password reset, user session. |
| `/assessments` | Maturity assessments, reports, interview guide generation. |
| `/respondent` | Passwordless client assessment flow. |
| `/reference` | Public authenticated reference data. |
| `/consultations` | Consultation request capture. |
| `/scraping` | Social listening jobs, status, reports, chat. |
| `/desk-research` | Uploads, extraction, reports, sessions, chat. |
| `/projects` | Projects, members, steps, artifacts. |
| `/shares` | Sharing analysis artifacts with users. |
| `/issue-log` | Issue log job creation, status, results, export. |
| `/admin/reference` | Admin reference data workflows. |
| `/admin/capability` | Admin capability and framework content. |
| `/admin/analytics` | Admin analytics and usage reporting. |

## 5. Request and Response Rules

- Request and response shapes are defined with Pydantic schemas in `backend/app/schemas/`.
- Routes should not expose internal ORM models directly.
- Ownership fields are derived from the authenticated user, not accepted from untrusted request bodies.
- Long-running operations should return a job id and expose polling endpoints.
- Duplicate assessment answer submissions should use idempotency behavior.

## 6. Error Handling

| Status | Meaning |
|---|---|
| `400` | Invalid input or unsupported operation. |
| `401` | Missing or invalid authentication. |
| `403` | Authenticated but not authorized. |
| `404` | Resource not found or not visible to caller. |
| `409` | State conflict, such as stale assessment version. |
| `422` | Schema validation failure. |
| `500` | Unexpected backend error. |

## 7. Background Job Pattern

Used by social listening and issue-log generation:

1. Client submits a run request.
2. API creates a database job row.
3. API returns job id immediately.
4. Backend runs work asynchronously.
5. Client polls status endpoint.
6. Result is read after completion.

## 8. API Quality Requirements

- Every route must have clear authentication and authorization behavior.
- Admin routes must resolve the admin dependency.
- Resource reads must check ownership, share visibility, or project membership.
- New routes should include tests when they touch security, jobs, persistence, or scoring.
