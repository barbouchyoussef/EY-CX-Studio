# Data Model: EY CX Studio

## 1. Overview

EY CX Studio uses PostgreSQL for relational application data and disk/object storage for large runtime artifacts. The database schema is defined by numbered SQL migrations in `backend/migrations/`. SQLAlchemy models mirror the schema but do not own table creation.

## 2. Main Entity Groups

| Group | Tables |
|---|---|
| Identity | `users`, `invites`, `refresh_tokens`, `password_reset_tokens` |
| Projects | `projects`, `project_members`, `project_steps`, `project_artifacts`, `analysis_shares` |
| Assessment | `assessments`, `assessment_answers`, `assessment_scores`, `assessment_axis_memory`, `assessment_insights`, `assessment_recipients`, `assessment_idempotency`, `assessment_website_audits`, `recommendation_outputs` |
| Interviews | `interview_guides`, `project_interview_reports` |
| Social listening | `scraping_jobs` |
| Issue log | `issue_logs`, `issue_log_jobs` |
| Reference data | `sectors`, `company_sizes`, `regions`, `axes`, `capabilities`, `maturity_levels`, `capability_maturity_rubrics`, `capability_recommendations`, `capability_quick_win_templates`, `axis_maturity_content`, `companies`, `company_sector_detections`, `company_size_detections` |
| Observability | `llm_calls` |

## 3. Identity Model

### `users`

Stores consultant and admin accounts.

Key fields:

- `id`
- `email`
- `full_name`
- `password_hash`
- `role`
- `status`
- `created_at`
- `updated_at`

Rules:

- Emails are unique.
- `password_hash` can be null before invite acceptance.
- Role controls admin access.

### `invites`

Stores invite tokens for invite-only signup.

Rules:

- Tokens expire.
- Accepted invites record `accepted_at`.

### `refresh_tokens`

Stores hashed refresh-token identifiers.

Rules:

- Raw refresh tokens are never persisted.
- Token families support rotation and reuse detection.

## 4. Project Model

### `projects`

Represents one client engagement.

Key fields:

- `id`
- `owner_id`
- `name`
- `company_id`
- `company_name`
- `sector`
- `created_at`
- `updated_at`

### `project_members`

Join table between projects and users.

Key fields:

- `project_id`
- `user_id`
- `role`
- `added_at`

### `project_steps`

Tracks pipeline step status for a project.

Key fields:

- `project_id`
- `step_key`
- `status`

### `project_artifacts`

Links module outputs to project steps.

Key fields:

- `id`
- `project_id`
- `step_key`
- `kind`
- `ref_id`
- `title`
- `created_by`
- `created_at`

Rules:

- `ref_id` is string-based because module ids are not all the same type.
- `kind` identifies whether the artifact is an assessment, desk research session, social report, interview guide, or issue log.

## 5. Assessment Model

### `assessments`

Stores assessment state and final report cache fields.

Key fields:

- `id`
- `owner_id`
- `company_id`
- `current_axis_id`
- `overall_maturity_level_id`
- `overall_maturity_band`
- `status`
- `state_version`
- `pending_question`
- `pending_options`
- `pending_focus_capability_id`
- `conversation_stage`
- `prompt_profile`
- `language`
- `leaders_snapshot_payload`
- `created_at`
- `updated_at`

Rules:

- `state_version` protects against concurrent answer submissions.
- `pending_question` and `pending_options` preserve the current turn.
- `language` supports bilingual output.

### `assessment_answers`

Stores conversation answers and evidence.

### `assessment_scores`

Stores capability-level scores, maturity levels, confidence, and evidence.

### `assessment_axis_memory`

Stores summarized per-axis memory used by the conversation engine.

### `assessment_recipients`

Stores client respondent links.

Rules:

- Link tokens are hashed.
- Tokens expire and can be revoked.

### `assessment_idempotency`

Stores idempotent responses for duplicate answer submissions.

## 6. Interview Model

### `interview_guides`

Stores generated guide content, edits, captured answers, and insight payloads.

### `project_interview_reports`

Stores project-level interview report outputs.

## 7. Desk Research Runtime Data

Desk research uses a combination of database/session metadata and storage keys for extracted content, generated reports, RAG chunks, and vectors.

Storage prefixes include:

- `desk_research_data/`
- `rag_data/`

Rules:

- Uploaded content and generated artifacts must be accessed through the storage service.
- RAG vector arrays are not stored in PostgreSQL.

## 8. Social Listening Model

### `scraping_jobs`

Stores job request data, status, progress, and result JSON.

Rules:

- Long-running scraping work updates job status.
- Frontend polling reads status and result payloads.

Storage prefix:

- `scraped_data/`

## 9. Issue Log Model

### `issue_logs`

Stores generated issue-log result payloads and metadata.

### `issue_log_jobs`

Stores background execution status for issue-log generation.

## 10. Reference Data Model

Reference tables define the CX framework:

- Axes: Manage, Analyze, Improve.
- Capabilities under each axis.
- Maturity levels.
- Capability rubrics.
- Recommendation and quick-win templates.
- Regions, sectors, company sizes, and companies.

Rules:

- Changes to scoring framework content should be made through migrations or admin-managed reference workflows.
- Rubrics and maturity content must stay aligned with scoring logic.

## 11. Validation Rules

- Database schema changes require a migration.
- Ownership fields are set server-side, not trusted from request bodies.
- Admin-only data changes require admin authorization.
- Project artifact references must point to visible resources.
- File-derived storage keys must remain inside their allowed prefixes.
- Generated issue taxonomy values must match the accepted taxonomy.
