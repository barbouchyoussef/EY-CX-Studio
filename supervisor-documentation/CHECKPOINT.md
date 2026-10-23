# Checkpoint: EY CX Studio

## Current Snapshot

- Date: 2026-09-15
- Product: EY CX Studio
- Status: Implemented full-stack application with documentation baseline in progress.
- Stack: FastAPI, PostgreSQL, React, TypeScript, Vite, Tailwind CSS.

## What Is Done

- Core README exists with overview, setup, configuration, tests, deployment, and module descriptions.
- Backend API is organized under `/api/v1`.
- Frontend module structure exists under `frontend/src/features/`.
- Authentication and invite-based access are implemented.
- Project workspace, membership, steps, and artifact attachment are implemented.
- Maturity assessment module is implemented.
- Interview guide module is implemented.
- Desk research module is implemented.
- Social listening module is implemented.
- Issue log module is implemented.
- Admin and analytics routes exist.
- Database migrations exist under `backend/migrations/`.
- Backend tests and frontend tests/check scripts exist.

## What Is Frozen

The following should not be changed casually while documentation and review are being prepared:

- Core module boundaries under `backend/app/services/` and `frontend/src/features/`.
- LLM gateway requirement for all model calls.
- Migration-owned database schema process.
- Authentication model using memory access tokens and rotating refresh cookies.
- Respondent flow based on scoped tokens.
- Project model as an overlay on modules rather than a required dependency.

## What Is In Progress

- Governance documentation requested by project leadership.
- Alignment between product, technical, architecture, data model, roadmap, and checkpoint documents.

## What Needs Verification

- Run backend test suite:

```bash
cd backend
python -m pytest
```

- Run frontend verification:

```bash
cd frontend
npm run verify
npm run lint
```

- Manually validate the main workflows:

```text
login -> create project -> run modules -> attach artifacts -> generate issue log -> export
```

## Known Dependencies

- PostgreSQL is required for the application database.
- LLM provider keys are required for generative features.
- Scraping provider tokens are required for social listening collection.
- SMTP is required for sending invites and password reset emails.
- Local embedding and document-processing models may download on first use.

## Next Steps

1. Review all documentation files with the project supervisor.
2. Run backend and frontend verification commands.
3. Record any failing checks or environment-specific blockers.
4. Complete one end-to-end pilot using representative project data.
5. Decide release readiness and remaining remediation tasks.

## Handoff Notes

- Start with `README.md` for setup and run commands.
- Use `DEEPDIVE.md` when changing implementation details.
- Use `docs/architecture/` for detailed feature-specific engineering notes.
- Keep new decisions in `DECISIONS.md`.
- Keep project status updates in this checkpoint file.
