# Database Specification: EY CX Studio

## 1. Overview

EY CX Studio uses PostgreSQL as its primary relational database. The schema is managed by numbered SQL migration files in `backend/migrations/`. SQLAlchemy models in `backend/app/db/models/` mirror the database but are not the schema authority.

## 2. Migration Strategy

- Migrations are numbered SQL files.
- `backend/seed.py` applies migrations in order.
- Applied migrations are recorded so the script is repeatable.
- Any schema change must include a new migration.
- ORM model changes without migrations are incomplete.

## 3. Core Table Groups

| Domain | Tables |
|---|---|
| Identity | `users`, `invites`, `refresh_tokens`, `password_reset_tokens` |
| Projects | `projects`, `project_members`, `project_steps`, `project_artifacts`, `analysis_shares` |
| Assessment | `assessments`, `assessment_answers`, `assessment_scores`, `assessment_axis_memory`, `assessment_insights`, `assessment_recipients`, `assessment_idempotency` |
| Interviews | `interview_guides`, `project_interview_reports` |
| Social listening | `scraping_jobs` |
| Issue log | `issue_logs`, `issue_log_jobs` |
| Reference data | `axes`, `capabilities`, `maturity_levels`, rubrics, sectors, sizes, regions, companies |
| Observability | `llm_calls` |

## 4. Relationship Summary

- A `user` owns projects and analysis records.
- A `project` has members, steps, and artifacts.
- A `project_artifact` points to a module output through `kind` and `ref_id`.
- An `assessment` belongs to a company and owner.
- Assessment answers and scores belong to an assessment.
- Interview guides can be generated from assessments or standalone setup data.
- Scraping and issue-log jobs store progress and result payloads.
- Reference data drives scoring, content, and dropdown values.

## 5. Data Validation Rules

- User emails must be unique.
- Password and refresh tokens are stored hashed where applicable.
- Assessment state version protects concurrent turn submissions.
- Respondent tokens are scoped and expirable.
- Project membership controls shared visibility.
- Issue-log taxonomy values must match the accepted taxonomy.
- Storage keys derived from request values must remain inside approved prefixes.

## 6. JSON Payload Usage

JSONB is used for flexible generated or external payloads, such as:

- Assessment pending options and benchmark payloads.
- Scraping job request and result data.
- Generated issue log payloads.
- Interview guide structured content.

JSONB should be used when generated structure changes faster than relational reporting needs. Highly queried stable data should remain relational.

## 7. Operational Notes

- PostgreSQL 13 or later is required.
- The application database is separate from the Metabase database in `docker-compose.yml`.
- Test configuration neutralizes environment settings to avoid production database access.
- Backups should include PostgreSQL plus configured object storage.
