# Project Context: EY CX Studio

## 1. Project Summary

EY CX Studio is an internal platform for customer experience consulting engagements. It combines maturity assessment, interview preparation, desk research, social listening, and issue-log consolidation into one project workspace.

## 2. Business Context

Consultants need to deliver CX diagnostics that are fast, consistent, evidence-based, and reusable across client engagements. The platform standardizes the workflow and reduces manual report assembly.

## 3. Core Product Modules

- Maturity assessment.
- Interview guide.
- Desk research.
- Social listening.
- Issue log.
- Project workspace.
- Admin and analytics.

## 4. Technical Context

- Backend: FastAPI and PostgreSQL.
- Frontend: React, TypeScript, Vite, Tailwind CSS.
- AI: Shared LLM gateway with usage logging.
- Retrieval: Local RAG with lexical fallback.
- Storage: Disk or production object storage.
- Deployment: Single Docker image serving API and frontend.

## 5. Important Constraints

- Access is invite-only.
- Client respondent flow uses scoped passwordless tokens.
- Database schema is migration-owned.
- LLM calls must use the gateway.
- Numbers in reports are computed in Python.
- Provider keys are required for many AI and scraping features.

## 6. Key Existing Documentation

- Root `README.md`: Product overview, setup, configuration, tests, deployment.
- Root `DEEPDIVE.md`: Implementation reference.
- `docs/architecture/`: Feature-level engineering notes.
- `supervisor-documentation/`: Supervisor-facing governance package.

## 7. Current Status

The application is implemented and has a substantial test suite. The current documentation effort packages product, engineering, project-management, and AI governance files for supervisor review.
