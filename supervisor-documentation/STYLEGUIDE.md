# Styleguide: EY CX Studio

## 1. General Principles

- Follow existing project patterns before introducing new ones.
- Keep changes focused and minimal.
- Prefer clear service boundaries over large cross-feature files.
- Make generated reports evidence-based and reviewable.
- Use English for code identifiers and technical documentation.

## 2. Backend Style

- Route modules belong in `backend/app/api/routes/`.
- Business logic belongs in `backend/app/services/`.
- Database access belongs in repositories where practical.
- Request and response models belong in `backend/app/schemas/`.
- Database schema changes require migrations.
- LLM calls must use the shared gateway.
- Long-running operations should use the existing job pattern.

## 3. Frontend Style

- Feature code belongs in `frontend/src/features/<feature>/`.
- Each feature should expose its public surface through `index.ts`.
- Shared components belong in `frontend/src/components/ui/`.
- Shared utilities belong in `frontend/src/lib/`.
- Prefer TypeScript types that match backend schemas.
- Keep module copy in feature-level copy files.

## 4. UI Style

- Keep operational screens clear and dense enough for consulting work.
- Use EY brand tokens consistently.
- Reuse shared buttons, headers, chat components, and dashboard patterns.
- Avoid decorative UI that does not help the workflow.
- Keep reports scannable with clear hierarchy and readable charts.

## 5. Documentation Style

- Use Markdown.
- Keep documents practical and implementation-aligned.
- Prefer tables for responsibilities, requirements, and checklists.
- Update documents when product behavior, architecture, or setup changes.

## 6. Naming Conventions

- Use descriptive file and function names.
- Use feature names consistently across frontend, backend, and documentation.
- Use uppercase hyphenated names for supervisor package files.
- Use lower-case Python module names and TypeScript project conventions in code.
