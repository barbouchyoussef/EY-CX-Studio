# Contributing: EY CX Studio

## 1. Contribution Workflow

1. Understand the target feature and read the related architecture notes.
2. Keep changes scoped to the requested task.
3. Update migrations for database changes.
4. Add or update tests for security, persistence, scoring, extraction, or shared behavior.
5. Run relevant checks.
6. Update documentation when behavior or setup changes.

## 2. Before Changing Code

- Read `README.md` for setup.
- Read `DEEPDIVE.md` for implementation paths.
- Read the relevant file in `docs/architecture/`.
- Check current git status so unrelated work is not overwritten.

## 3. Backend Contributions

- Add routes under `backend/app/api/routes/`.
- Use Pydantic schemas for request and response data.
- Keep route handlers thin.
- Use services for business logic.
- Use repositories or unit-of-work patterns for persistence.
- Add migrations for schema changes.
- Use the LLM gateway for model calls.

## 4. Frontend Contributions

- Add module code under `frontend/src/features/`.
- Keep feature internals private behind `index.ts`.
- Use shared API helpers for requests.
- Keep access-token behavior unchanged.
- Update feature copy files for user-facing text.
- Run typecheck and build before release.

## 5. Testing Expectations

Backend:

```bash
cd backend
python -m pytest
```

Frontend:

```bash
cd frontend
npm run verify
npm run lint
```

## 6. Documentation Expectations

Update the supervisor package when changing:

- Product behavior.
- API behavior.
- Database model.
- Security model.
- Deployment process.
- AI usage rules.
- Release or roadmap scope.

## 7. Pull Request Checklist

- Scope is clear.
- Tests were added or rationale is documented.
- Relevant checks pass.
- Migrations are included when needed.
- No secrets or runtime artifacts are committed.
- Documentation is updated.
