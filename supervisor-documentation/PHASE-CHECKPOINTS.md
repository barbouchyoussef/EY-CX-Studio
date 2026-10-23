# Phase Checkpoints: EY CX Studio

## Phase 1: Documentation Package

Status: Complete when supervisor documentation files exist and are reviewed.

Checklist:

- Core project files created.
- Engineering files created.
- Product-specific files created.
- Project-management files created.
- AI files created.
- All files centralized in `supervisor-documentation/`.

## Phase 2: Technical Verification

Status: Pending.

Checklist:

- Backend dependencies install.
- Backend tests pass.
- Frontend dependencies install.
- Frontend verification passes.
- Linting passes or issues are documented.
- Database migrations apply successfully.

Commands:

```bash
cd backend
python -m pytest
```

```bash
cd frontend
npm run verify
npm run lint
```

## Phase 3: Functional Smoke Test

Status: Pending.

Checklist:

- Consultant login works.
- Project creation works.
- Maturity assessment starts and completes.
- Respondent link works.
- Interview guide generates and saves.
- Desk research upload produces report.
- Social listening job runs with configured tokens.
- Issue log generates from selected sources.
- Exports work.
- Admin access is restricted.

## Phase 4: Security Review

Status: Pending.

Checklist:

- No secrets committed.
- Production `JWT_SECRET` configured.
- Cookie settings reviewed.
- Admin routes protected.
- Resource access checks reviewed.
- Respondent token behavior reviewed.
- Provider and tracing data policies approved.

## Phase 5: Deployment Readiness

Status: Pending.

Checklist:

- Docker image builds.
- Environment file validated.
- Migrations run in target environment.
- First admin account created.
- Health endpoint responds.
- Frontend served correctly.
- Login works over HTTPS.
- Rollback plan confirmed.

## Phase 6: Pilot Review

Status: Pending.

Checklist:

- Pilot project created.
- At least three modules used.
- Issue log generated.
- Deliverables reviewed by consultant.
- Bugs triaged.
- Supervisor accepts or requests remediation.
