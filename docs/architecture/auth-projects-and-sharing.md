# Auth, Projects & Sharing (cross-cutting)

The identity, authorization, project, and sharing layer that every module sits on. Code:
`backend/app/services/auth/`, `backend/app/services/projects/`,
`backend/app/api/routes/{auth,projects,shares}.py`; frontend `src/context/`, `src/lib/`.

## Authentication

Invite-only, email + password. **No open signup.**

- **Passwords:** bcrypt (with a SHA-256 pre-hash to defeat bcrypt's 72-byte truncation). Policy: min
  8 chars, ≥1 letter, ≥1 number (`app/schemas/auth.py`).
- **Tokens (locked design):** a short-lived **access token held in memory** on the client + a
  **rotating refresh token in an `HttpOnly; Secure; SameSite=Strict` cookie**. Refresh rotates on
  every use with **reuse detection** (a replayed old `jti` revokes the family). This keeps the
  long-lived credential unreadable to XSS. JWT is HS256, `algorithms` pinned on decode.
- **Routes** (`app/api/routes/auth.py`): `POST /auth/login`, `/auth/refresh`, `/auth/logout`, `GET /auth/me`,
  `POST /auth/invite` (create `Invite`), `POST /auth/accept` (activate + set password), plus
  forgot/reset password.
- **Roles:** `admin` | `consultant`. A non-admin inviter can only mint consultant invites; role
  changes are admin-only.
- **Bootstrap:** `python -m app.scripts.create_admin` (reads `ADMIN_EMAIL` / `ADMIN_PASSWORD`),
  idempotent — re-run to reset the admin password.
- **Dependency:** `app/dependencies/auth.py` — `get_current_user` (decode Bearer → active user),
  `require_admin`.
- **Frontend:** `src/lib/api.ts` `authFetch`/`authFetchUrl` inject the in-memory access token, send
  the refresh cookie (`credentials: "include"`), and on `401` call `/auth/refresh` once then retry.
  `src/context/AuthContext.tsx` restores a session on load via a silent refresh.

## Authorization — the single brain

`app/services/auth/access.py` is the one place authorization decisions live. Every list/read/mutate
routes through it — deny by default.

- `visible_refs(user, kind)` → the set of `ref_id`s of a given kind the user may see: **owned ∪
  shared ∪ attached-to-a-project-they're-a-member-of**.
- `can_view_via_project_or_share(...)` → single-record check for the non-owner case.
- `owner_id` is always set server-side to the caller; request schemas never accept it (no mass
  assignment). Only the owner can delete or share; a shared recipient can open but not delete/re-share.

Every dashboard surfaces this: a row the caller doesn't own is tagged **"Shared with you"**, and
Share/Delete are hidden on it. The list endpoints return an `owned` boolean per row (assessments,
interview guides, social reports, desk sessions).

## Projects (the anchor)

Projects moved from JSON files to Postgres. Tables:

- `projects` (owner_id, name, company_id/name, sector).
- `project_members` (project_id, user_id, role `owner|collaborator`).
- `project_steps` (per pipeline step: `assessment`, `interview`, `social`, `desk_research`; status).
- `project_artifacts` (**the indirection that links any module's output**): `kind ∈ {assessment,
  interview_guide, desk_session, social_report}`, `ref_id` (int PK as text / session id / report
  filename), `step_key`, `title`. One-to-many, so a project can hold several runs of the same tool.

`app/services/projects/project_service.py`: create/list (scoped to owned+member), members
(add/remove, owner immutable), `add_artifact` (idempotent attach), `detach_artifact`,
`cleanup_analysis_links` (on delete). Routes in `app/api/routes/projects.py`.

**Project-native flow (frontend):** `src/context/ActiveProjectContext.tsx` lifts the active project
to the app root; a module, on producing a result, calls `attach(kind, refId, title)` +
`completeStep(stepKey)`, so a finished run lands *in* the project and flips the pipeline node green.
The floating `ProjectStepNav` shows the numbered pipeline (assessment → interview → social → desk
research) across modules.

## Sharing

Per-analysis sharing, independent of projects:

- `analysis_shares` (kind, ref_id, shared_by, shared_with, `UNIQUE(kind, ref_id, shared_with)` so a
  double-share is idempotent). Routes: `POST /shares`, `DELETE /shares/{id}`, `GET /shared-with-me`.
- Frontend `ShareButton` (`src/components/ui/share-button.tsx`) — a popover to share by email and
  list/revoke recipients — is reused on every module's dashboard row (owner only). You can only share
  something you can already view.

## Security posture (summary)

Deny-by-default authorization; owner-set identity (no mass assignment); enumeration-resistant login;
JWT pinned algorithm + short expiry + refresh rotation with reuse detection; invites single-use +
expiring + role-bound; path-traversal guards on the file stores; secrets via env only. Deferred:
login rate-limiting.

## Migrations

Hand-written numbered SQL in `backend/migrations/`, applied idempotently by `backend/seed.py`
(`run_migrations()`, tracks `migration_history`). New files continue the number sequence. No Alembic.
