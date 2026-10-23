# Maturity Assessment & Interview Guides

Code: `backend/app/services/assessment/`. Routes: `backend/app/api/routes/assessments.py`
(consultant) and `respondent.py` (passwordless client). UIs:
`frontend/src/features/assessment/hub.tsx`, `features/interview/hub.tsx`, and
`frontend/src/features/assessment/client/` (client-facing assessment).

## A. Maturity Assessment

A conversational CX-maturity diagnostic. The assessment is scored across three axes —
**MANAGE · ANALYZE · IMPROVE** — and produces an executive report with an overall maturity band.

### Flow
1. **Onboarding / company profile** — company name, sector, company size, region (structured
   context, not guessed from the name). `POST /assessments` (`lifecycle_service.start_assessment`)
   creates the company + assessment, stamps `owner_id`.
2. **Guided Q&A loop** — `GET /assessments/{id}/next-question` → `POST /answers`, repeated. Driven by
   `conversation_service`; each answer updates per-axis progress (covered/total).
3. **Completion & report** — on the last answer the assessment flips to `completed`;
   `GET /assessments/{id}/final-report` (`reporting_service` / `final_report_service`) generates the
   report **on demand** (finalizes recommendations + maturity band). Report contains hero, axis
   scores, capabilities, leaders snapshot, quick-wins timeline, recommendations
   (`frontend/src/features/assessment/report/AssessmentReport.tsx`).

### Passwordless client links (the "second actor")
A consultant can send the assessment to an external client who has **no account**:

- **Mint:** `POST /assessments/{id}/recipients` (`client_link_service`) creates an
  `assessment_recipients` row storing only the token **hash** (SHA-256), scoped to that one
  assessment. Returns the link `{APP_BASE_URL}/a/<raw-token>` (optionally emailed).
- **Respondent path:** `app/api/routes/respondent.py` — **no `get_current_user`**. The client sends
  the token as `X-Respondent-Token`; `_ctx` resolves it to exactly one assessment (401 otherwise) and
  marks it opened. Endpoints: `GET /respondent/context`, `POST /respondent/profile` (client sets their
  own sector/size), `GET /respondent/next-question`, `POST /respondent/answers`,
  `GET /respondent/final-report` (marks completed). It can never reach a consultant route or another
  assessment.
- **Client UI:** `frontend/src/features/assessment/client/` — a public route `/a/<token>` (mounted before the
  auth gate in `App.tsx`). A "hello" company-profile step (client fills their own sector/size) → the
  chat (mirrors the consultant chat: axes sidebar, boxed options, avatar bubbles) → the **full report**
  at the end. `respondentApi.ts` uses plain fetch + the token header (no login).
- **Consultant dashboard** shows each assessment's recipient (name/role) and status
  (**Link sent → Opened by client → Completed**); "Resume" is replaced by "Awaiting client" for
  unfinished client links.

### Key services
`lifecycle_service` (start/list/get), `conversation_service` (Q&A), `scoring_service` (axis scores +
overall band), `reporting_service` / `final_report_service` (report), `client_link_service`
(recipients/tokens).

### The recommendation content model

`capability_recommendations` (one row per capability x maturity level, seeded by
`migrations/017_seed_extended_capability_content.sql`) is what steers the report prompt. The
columns are bare `VARCHAR`/`TEXT` with no constraint, so what each one means lives here:

| Column | Holds |
|---|---|
| `recommendation_guideline` | The core recommendation direction injected into the final report prompt |
| `priority_hint` | Urgency framing: `urgent_foundation`, `build_consistency`, or `scale_advantage` |
| `business_impact` | The customer or business outcome expected from acting on the recommendation |
| `tone_hint` | Preferred report tone: `direct`, `balanced`, or `executive` |
| `consultant_note` | Optional nuance used to frame the final wording |
| `evidence_to_cite` | What the report should point at as justification |
| `initiative_suggestions` | Concrete initiatives offered as starting points |

A related column on `capabilities`, `question_guidelines`, is internal guidance that helps the
model generate better assessment questions. It is not a script shown to the respondent.

## B. Interview Guides

Generates a tailored stakeholder interview guide, optionally grounded in a maturity assessment.

This is the overview. [interview-guides.md](interview-guides.md) is the full module
reference: endpoints, the generation flow function by function, and the two assistants.

### Flow
1. **Source & company** — start *from scratch* or *from an existing assessment* (grounds the guide in
   that assessment's conversation/state). Company + target persona/profile.
2. **Generate** — produces an `InterviewGuideResponse` with five question sections
   (introduction / manage / analyze / improve / closure); each question has rationale, follow-ups,
   and space for the consultant's answer notes.
3. **Persist** — saved to the `interview_guides` table (`owner_id`, `assessment_id`, `payload` JSONB,
   `insights` JSONB). Upsert is by explicit `id` (two guides for the same company+profile are two
   rows, not an overwrite).
4. **Insights** — `POST /assessments/interview-guide/insights` (`interview_insights.generate_insights`)
   cross-references the underlying assessment's conversation **trace** against the interview
   **answers** the consultant filled in, and **persists** the briefing on the guide so history shows
   it without regenerating.

### Dashboard
`features/interview/history-table.tsx` — Company · Profile · **Questions count** · Insights (click → open) ·
Updated, plus a sub-line with **owner** and **source** ("from a maturity assessment" / "from
scratch"). Open / Share / Delete / Import + "New interview" → the Step-1 wizard.

## Data model & ownership
Both assessments and interview guides live in Postgres with `owner_id`; visibility is via
`access.py` (own / shared / project). See [auth-projects-and-sharing.md](auth-projects-and-sharing.md).
