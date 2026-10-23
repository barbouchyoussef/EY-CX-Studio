# Testing: EY CX Studio

## 1. Testing Strategy

Testing focuses on backend business rules, security boundaries, storage safety, scoring behavior, extraction resilience, and frontend correctness for shared utilities and critical flows.

## 2. Backend Tests

Backend tests live in `backend/tests/` and run with Pytest.

Command:

```bash
cd backend
python -m pytest
```

Important coverage areas:

- Authentication and authorization.
- Admin route protection.
- Assessment scoring and state transitions.
- Idempotency behavior.
- Desk research extraction and persistence.
- RAG chunking and retrieval.
- Social listening analytics and report grounding.
- Issue-log generation and citation behavior.
- Storage path safety.
- LLM gateway retry and service contracts.

## 3. Frontend Tests

Frontend tests use Vitest and React Testing Library.

Commands:

```bash
cd frontend
npm run test
npm run verify
npm run lint
```

`npm run verify` includes:

- TypeScript build check.
- Brand token consistency check.
- Frontend tests.
- Production build.

## 4. Manual Test Scenarios

- Sign in as consultant.
- Create a project.
- Run a maturity assessment.
- Generate a final report.
- Open respondent link and answer as client.
- Generate and edit an interview guide.
- Upload documents to desk research and ask report questions.
- Run social listening with configured tokens.
- Generate issue log from multiple sources.
- Export reports or workbooks.
- Verify unauthorized users cannot access private resources.

## 5. Test Data Rules

- Do not use production client data in local tests.
- Use anonymized or synthetic files for extraction testing.
- Test environment configuration should not point to production services.
- Provider keys used for manual testing must be stored in local `.env`, not committed.

## 6. Definition of Passing

- Backend tests pass.
- Frontend `npm run verify` passes.
- Frontend lint either passes or documented lint findings are accepted.
- Critical manual workflows pass in the target environment.
- Known failures are recorded before release.
