# Execution Rules: EY CX Studio

## 1. Engineering Execution Rules

- Start from existing patterns.
- Keep changes scoped.
- Do not rewrite working modules without a clear reason.
- Add migrations for schema changes.
- Run relevant tests before release.
- Update documentation when behavior changes.

## 2. Backend Rules

- Routes stay thin.
- Services own business logic.
- Repositories own database access where practical.
- Unit-of-work boundaries control coordinated writes.
- All LLM calls use the shared gateway.
- Background jobs use persisted job status and polling.
- Storage access goes through the storage service.

## 3. Frontend Rules

- Feature code stays inside its feature folder.
- Public feature imports go through `index.ts`.
- Shared UI goes in `components/ui`.
- API calls use shared API helpers.
- Access tokens must not be persisted in browser storage.
- Brand tokens must remain synchronized.

## 4. Security Rules

- Do not weaken authentication.
- Do not bypass access checks.
- Do not expose raw respondent tokens.
- Do not log provider credentials.
- Do not commit secrets.
- Admin routes require admin authorization.

## 5. AI Rules

- Models explain computed data; they do not create metrics.
- Generated reports require review.
- Recommendations must be evidence-aware.
- Provider failures should be clear to the user or operator.
- Tracing with client data requires approval.

## 6. Release Rules

- No release with known critical security issues.
- No release when login is broken.
- No release when migrations fail.
- No release when core workflows cannot be completed.
- Document accepted risks before release.
