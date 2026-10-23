# CX Studio: codebase reference

This document is for changing the code. The README covers what the platform is and how to run it.

Part 1 covers the machinery every feature sits on. Part 2 covers the features themselves, one
chapter each, tracing the path a request takes and listing the files that implement it. Part 3 is
reference material.

`docs/architecture/` holds a longer document per feature, written while each was built. This file
is the map; those are the detail.

## Contents

**Part 1: Foundations**
[Request path](#request-path) ·
[Authentication and access](#authentication-and-access) ·
[The language model layer](#the-language-model-layer) ·
[Retrieval](#retrieval) ·
[Storage](#storage) ·
[Background jobs](#background-jobs) ·
[Frontend](#frontend)

**Part 2: Features**
[Maturity assessment](#maturity-assessment) ·
[Interview guides](#interview-guides) ·
[Desk research](#desk-research) ·
[Social listening](#social-listening) ·
[Issue log](#issue-log) ·
[Projects](#projects)

**Part 3: Reference**
[Database](#database) ·
[Configuration](#configuration) ·
[API surface](#api-surface) ·
[Tests](#tests)

# Part 1: Foundations

## Request path

Routers live in `backend/app/api/routes/`, one file per area, each registered in
`app/api/router.py` under `/api/v1`. A route resolves its dependencies, calls a service, and
returns a Pydantic model from `app/schemas/`.

Services are constructed per request by a factory rather than injected as singletons. For the
assessment that is `app/services/assessment/factory.py`, which wires the repositories, the LLM
service and the unit of work together. Repositories in `app/repositories/` own the SQL; a service
that reaches for `db.execute` directly is a smell, and the report service was cleaned of its last
one.

Writes go through `AsyncUnitOfWork` (`app/services/platform/unit_of_work.py`), which owns the
transaction boundary. `async with self.uow:` commits on exit and rolls back on exception.

Two decorators attach cross-cutting behaviour at the service layer rather than the route:
`@idempotent_request` (`app/services/platform/idempotency.py`) replays a stored response when the
same `Idempotency-Key` arrives twice, and `llm_context` (`app/services/observability/llm_metrics.py`)
tags every model call made inside its block with the feature that caused it.

## Authentication and access

There is no open sign up. `app/scripts/create_admin.py` creates the first account; everyone else
arrives through an invite.

The token pair is a short-lived access token held in memory by the browser and a rotating refresh
token in an `HttpOnly` cookie. `frontend/src/lib/api.ts` holds the access token in a module
variable, never in `localStorage`, so an XSS bug cannot read a durable session. On a 401 it calls
`/auth/refresh` once, retries, and on failure clears the token and redirects. Refresh rotates the
`jti` and detects reuse: replaying a rotated token revokes the whole family.

`app/services/auth/access.py` is the only place that decides whether a caller may see something.
Three questions, in order: do they own it, is it shared with them through `analysis_shares`, or is
it attached to a project they are a member of. Every list endpoint scopes through
`list_visible`, every single-record read through `can_view`. Ownership is always set server side
from the authenticated user; request schemas do not carry `owner_id`.

Clients answering an assessment do not have accounts. `app/api/routes/respondent.py` accepts a link
token, resolves it to exactly one assessment through `app/services/assessment/client_link_service.py`,
and exposes only that assessment's turn and answer endpoints. The token is stored as a SHA-256
hash, expires, and is revocable.

| File | Contents |
|---|---|
| `app/services/auth/security.py` | Password hashing, token minting and decoding |
| `app/services/auth/service.py` | Login, invite, accept, password reset |
| `app/services/auth/access.py` | `owns_analysis`, `can_view`, `list_visible`, `visible_project_ids` |
| `app/dependencies/auth.py` | `get_current_user`, `require_admin` |
| `app/api/routes/auth.py` | The endpoints |
| `frontend/src/lib/api.ts` | `authFetch`, token holder, refresh-on-401 |
| `frontend/src/context/AuthContext.tsx` | Session restore on load, login and logout |

## The language model layer

Every model call goes through `MistralGateway.chat_messages` in
`app/services/llm/core/gateway.py`. This is not a style preference: the gateway is where usage is
recorded into `llm_calls`, so a caller that builds its own HTTP request produces no cost data. If
a feature's spend is missing from the dashboard, check that first.

The same seam mirrors each call to **Langfuse** when `LANGFUSE_PUBLIC_KEY` and
`LANGFUSE_SECRET_KEY` are set (`_emit_langfuse` in `llm_metrics.py`). This is the one place that
sees the actual prompt and response text; the `llm_calls` row holds only counts and outcome. An
`llm_context` block opens one trace, so a multi-call operation reads as a single trace rather than
as scattered generations. It is a no-op without the keys, and it is configured in production, so
prompt and response content for real client material leaves the platform to Langfuse Cloud.

The retry policy lives there once for all call sites. Four attempts, retrying only 429 and 5xx, a
400 failing immediately. A rate limit backs off harder than a server error, and a provider's own
`Retry-After` header overrides the computed delay. `app/services/llm/throttle.py` books capacity
against a shared budget for the benchmark, which fires many calls at once; ordinary calls are not
throttled.

`app/services/llm/core/facade_service.py` is what features call. Underneath it:

| Module | Responsibility |
|---|---|
| `llm/conversation/question_composer.py` | Composes the next assessment question from the axis, the memory and the rubrics |
| `llm/conversation/memory_service.py` | Maintains the running per-axis summary, capped at eight lines |
| `llm/intent/router.py` | Classifies a message as VALID_ANSWER, CONFUSION, RESUME or LOW_QUALITY, with a deterministic fast path before the model |
| `llm/coverage/detector.py` | Decides which criteria an answer evidences, against the framework's rubrics |
| `llm/reporting/report_synthesis.py` | The report narrative |
| `llm/reporting/recommendation_generator.py` | Single and batched recommendation text |
| `llm/classification/company_classification.py` | Infers sector and size from a company name |
| `llm/prompts/templates.py` | Prompt text |
| `llm/utils/parsing.py` | `extract_json`, which scans a response for the first decodable object |

Nothing computes a number. Reports pass statistics calculated in Python into the prompt and ask
for prose around them, which is what makes a report reproducible across runs.

## Retrieval

`app/services/rag/` is shared by the module chatbots.

`chunker.py` splits documents, `embeddings.py` wraps `multilingual-e5-small` locally,
`store.py` persists chunks as JSON and vectors as a numpy array through the storage layer, and
`engine.py` answers a query: plan, retrieve, answer with citations. There is no vector database.
At these volumes a numpy dot product over a loaded array is enough, and it removes a service from
the deployment.

Retrieval degrades rather than failing. If `sentence-transformers` is unavailable, `store.py`
falls back to lexical matching and the chatbots keep working.

Not every module retrieves. The engine takes a **context source**, and each module supplies a
different one:

| Module | Context source |
|---|---|
| Desk research | Vector retrieval over the uploaded documents and the generated report |
| Social listening | The report's computed statistics, injected whole (`scraping/social_chat.py`) |
| Interview guides | The current guide, sent on every turn so the assistant sees live edits |

Social injects rather than retrieves because a report is a few kilobytes and any question about it
may touch any part. Retrieval would risk missing a section for no saving.

## Storage

`app/services/storage.py` selects a backend from `STORAGE_BACKEND`: `DiskBackend` in development,
`SupabaseBackend` in production. Callers use `put_bytes`, `get_text`, `exists`, `list_keys`,
`delete` and never touch a path.

The backend is built lazily on first use, not at import, so a storage misconfiguration surfaces on
the first storage call rather than taking down login and the frontend at startup.

What lives where:

- **PostgreSQL**: users, invites, projects and their members, steps and artifacts, shares,
  assessments and everything hanging off them, interview guides, scraping jobs including their
  result payload, issue logs, reference data, `llm_calls`.
- **Object storage**: desk research sessions and their extracted documents, social report JSON,
  RAG chunks and vectors. Keys are prefixed `desk_research_data/`, `scraped_data/`, `rag_data/`.

## Background jobs

A scraping run or an issue-log run takes minutes and exceeds what a reverse proxy holds open.
Both run as jobs.

The pattern is the same in `scraping/job_service.py` and `issue_log/job_service.py`: create the
row first so a fast failure has somewhere to report itself, start an `asyncio` task that owns its
own short-lived sessions, and let the browser poll a status endpoint. A semaphore bounds
concurrent runs. Both keep their tasks in a module-level set, because asyncio holds only weak
references and an unreferenced task can be collected mid-run.

The frontend remembers the running job id, so closing the tab and returning rejoins the run rather
than losing it. See `readActiveJobId` in `features/social/hub.tsx`.

## Frontend

`src/features/` holds one folder per module plus `projects`, `admin` and `auth`. Each has an
`index.ts` naming what the rest of the application may import; everything else in the folder is
internal to it. `App.tsx` imports the module, not a path into it.

Routing is hand-rolled in `App.tsx` on `pathname.startsWith`, with `navigateTo` pushing state.
There is no router library.

`src/components/ui/` holds only what more than one feature uses: the chat, the module header, the
share and add-to-project buttons, the studio nav, and a few visual primitives.

Shared conventions:

| Concern | Where |
|---|---|
| Bilingual copy | A `copy.ts` per module. `lib/dashboard-copy.ts` holds the words all dashboards share, spread into each module's table |
| Brand colours | `@theme` tokens in `index.css`, giving `bg-ey-navy` and so on. `lib/brand.ts` holds the same palette for chart data, and `npm run check:brand` fails the build if the two disagree |
| Button styles | Six repeated patterns named in `index.css` (`btn-secondary`, `btn-icon`, and so on). One-off styles stay inline |
| Project attachment | `lib/use-project-artifacts.ts` provides both hooks; the four dashboards use them rather than each fetching |
| Errors | `lib/errors.ts` reads a message from anything thrown, including API error bodies |

# Part 2: Features

## Maturity assessment

A conversational diagnostic scoring nine capabilities across three axes (Manage, Analyze,
Improve) against the framework's rubrics, ending in a report with quick wins, recommendations and
a competitor benchmark. It runs either with a consultant driving it or through a passwordless link
sent to the client.

### The path through the code

`POST /assessments` reaches `lifecycle_service.start_assessment`, which resolves the company,
creates the assessment row and calls `scoring.initialize_scores` to write one unscored row per
capability.

Each turn is `POST /assessments/{id}/answers`, arriving at
`conversation/service.submit_answer`. That method carries `@idempotent_request`, so a repeated
`Idempotency-Key` returns the stored response instead of scoring twice. It delegates to
`answer_flow_service.submit_answer`, which:

1. takes the assessment with `get_by_id_for_update`, holding a row lock so two tabs cannot both
   score the same version;
2. asserts the caller's expected axis and version, returning 409 on a mismatch;
3. classifies the message through `llm.route_user_intent`. A confused or low-quality message is
   handled by `handle_non_valid_intent` and never scored; a resume request by
   `handle_resume_intent`;
4. for a valid answer, calls `process_valid_answer`: coverage detection decides which criteria the
   answer evidences, `scoring_service.persist_scoring` writes the maturity level and confidence,
   and `memory_sync_service` updates the axis summary.

The next question comes from `question_flow_service.next_question`. It re-sends a pending question
unless a follow-up hint means it needs rewording, checks whether the axis has heard enough to
advance, resolves any outstanding follow-up, then asks the composer for a new question. Which
capability it asks about is scored rather than fixed: `select_question_focus` starts from a
designed order and adjusts it, pushing back what memory shows is covered and pulling forward what
the last answer gestured at.

The final report is assembled by `reporting/final_report_service.get_final_report`, which gathers
scores, capability evidence, recommendations, quick wins and the benchmark into one payload. The
benchmark is the expensive part: `telecom_semantic_leaders_service` searches for evidence per
candidate leader, reranks it against the client's weakest capabilities, filters sources for
credibility, and has the model write the comparison.

### Files

| File | Contents |
|---|---|
| `services/assessment/factory.py` | Builds the service graph for a request |
| `services/assessment/lifecycle_service.py` | `start_assessment`, `get_assessment`, `list_assessments`, `get_messages` |
| `services/assessment/conversation/service.py` | `next_question`, `submit_answer`, the idempotency and metering boundary |
| `services/assessment/conversation/answer_flow_service.py` | `submit_answer`, `process_valid_answer`, intent branches |
| `services/assessment/conversation/question_flow_service.py` | `next_question`, `select_question_focus`, follow-up resolution |
| `services/assessment/conversation/memory_sync_service.py` | Keeps the per-axis summary current |
| `services/assessment/scoring/scoring_service.py` | `persist_scoring`, `resolve_confidence`, `compute_overall_maturity_band` |
| `services/assessment/state/state_service.py` | Axis progression, `assert_expected_state`, completion |
| `services/assessment/reporting/final_report_service.py` | `get_final_report`, axis scoring, quick-win selection, hero copy |
| `services/assessment/reporting/recommendation_service.py` | `_generate_recommendations_batch`, the evidence gate |
| `services/assessment/reporting/telecom_semantic_leaders_service.py` | Candidate research, rerank, credibility filter, EY insights card |
| `services/assessment/reporting/sector_leader_candidates.py` | The curated shortlist per sector |
| `services/assessment/client_link_service.py` | Recipient links, `latest_recipient_by_assessment` |
| `api/routes/assessments.py` | Consultant endpoints |
| `api/routes/respondent.py` | The client link path |
| `frontend/src/features/assessment/hub.tsx` | Consultant chat and dashboard |
| `frontend/src/features/assessment/client/` | The passwordless client page and its chat |
| `frontend/src/features/assessment/report/` | Report sections, the radar, the PDF |

### Where to change what

| Task | File |
|---|---|
| Reword a question the assistant asks | `llm/prompts/templates.py` |
| Change how a capability is scored | `assessment/scoring/scoring_service.py` |
| Change which capability is asked about next | `question_flow_service.select_question_focus` |
| Change when an axis is finished | `assessment/state/state_service.py` |
| Add or reword report copy | `frontend/src/features/assessment/report/copy.ts` |
| Change the quick-win selection rule | `final_report_service._spread_quick_wins_across_axes` |
| Add a sector's benchmark candidates | `reporting/sector_leader_candidates.py` |
| Change the recommendation evidence gate | `recommendation_service._too_thin_to_recommend` |

## Interview guides

Generates a stakeholder interview guide, either grounded in a completed assessment or from
scratch. The guide is editable in place, answers are captured against each question, and an
assistant cross-references those answers with the assessment.

### The path through the code

`POST /assessments/interview-guide/generate` collects the company context and, when an assessment
is chosen as the source, its scores and gaps. The model returns five sections of questions;
`withQuestionIds` on the frontend fills in the ids and defaults the UI depends on.

Saving is `POST /assessments/interview-guide/save`, which upserts by explicit id. The frontend
autosaves: `localStorage` immediately, and the database after 1.5 seconds of no editing.

The assistant is `services/assessment/interview_chat.py`. Every turn sends the current guide
rather than a stored copy, so it reasons over unsaved edits.

Insights are `services/assessment/interview_insights.py`, comparing captured answers against the
assessment conversation and persisting the result on the guide so reopening does not regenerate.

### Files

| File | Contents |
|---|---|
| `services/assessment/interview_chat.py` | The assistant, guide injected per turn |
| `services/assessment/interview_chat_store.py` | Conversation persistence |
| `services/assessment/interview_insights.py` | `generate_insights` |
| `services/assessment/interview_findings.py` | Structured findings for the issue log |
| `schemas/interview_guide.py` | Guide and list-item shapes |
| `frontend/src/features/interview/hub.tsx` | The page: setup, result, editing, chat |
| `frontend/src/features/interview/guide.ts` | Types, `withQuestionIds`, `questionsFieldFor` |
| `frontend/src/features/interview/setup.ts` | Validation rules per form step |
| `frontend/src/features/interview/excel.ts` | The workbook export |
| `frontend/src/features/interview/copy.tsx` | All copy, both languages |

### Where to change what

| Task | File |
|---|---|
| Change the generated guide's shape | `llm/prompts/templates.py` and `schemas/interview_guide.py` |
| Add a persona | `frontend/src/features/interview/copy.tsx` |
| Change setup validation | `frontend/src/features/interview/setup.ts` |
| Change the Excel deliverable | `frontend/src/features/interview/excel.ts` |
| Change what the assistant sees | `services/assessment/interview_chat.py` |

## Desk research

Accepts client documents, extracts them, and produces a structured report. A chatbot answers over
both the documents and the report.

### The path through the code

`POST /desk-research/upload` reaches `desk_research/pipeline.process_files`. Per file,
`converter.py` picks a docling pipeline by format, then `extractor.extract` turns the result into
blocks and markdown.

Extraction has three layers, and a file has to defeat all of them to come back empty. A PDF with a
text layer skips docling entirely through `extract_pdf_native`. If docling returns under
`_THIN_OUTPUT_CHARS`, `_rescue_thin_extraction` reads natively with pypdfium2 or python-pptx,
covering only pages docling did not reach. Pages that still have no text are genuinely scanned and
are OCR'd one at a time, capped at 25.

Images are described by `gemini_vlm.py`, which rotates several keys, puts a rate-limited key on
cooldown rather than retrying it, tries several models, then fails over to OpenRouter. A 200 with
no usable text counts as a failure and falls through.

Extracted text is indexed by `rag_index.py` for the chatbot. The report is
`synthesizer.generate_executive_report`: a per-document pass, a reduce into the narrative, and a
structured CX mapping that the issue log consumes.

### Files

| File | Contents |
|---|---|
| `services/desk_research/pipeline.py` | `process_files`, `process_file`, persistence |
| `services/desk_research/converter.py` | Docling configuration, format to pipeline |
| `services/desk_research/extractor.py` | `extract`, the rescue passes, table compaction |
| `services/desk_research/gemini_vlm.py` | `describe_image`, key rotation and failover |
| `services/desk_research/synthesizer.py` | `generate_executive_report`, the CX mapping |
| `services/desk_research/session_manager.py` | Sessions, chat history, storage keys |
| `services/desk_research/rag_index.py` | Indexing documents and the report |
| `frontend/src/features/desk-research/hub.tsx` | Upload, progress, report, chat |
| `frontend/src/features/desk-research/markdown.tsx` | The report renderer |
| `frontend/src/features/desk-research/pdf-export.ts` | The print document |

### Where to change what

| Task | File |
|---|---|
| Accept a new file format | `converter.py` (`_EXT_TO_FORMAT`) and `extractor.py` |
| Change OCR languages | `DESK_OCR_LANGS`, read by `converter.py` |
| Change the report's structure | `synthesizer.py` |
| Change what the chatbot retrieves | `rag_index.py` and `services/rag/engine.py` |
| Change the on-screen report rendering | `features/desk-research/markdown.tsx` |
| Change the PDF | `features/desk-research/pdf-export.ts` |

## Social listening

Collects public reviews and posts, classifies each, and reports on the aggregate. A consultant can
also supply a manual analysis workbook for channels that cannot be scraped.

### The path through the code

`POST /scraping/run` creates a job and returns immediately. The task calls
`scraping_service.py`, which has a scraper per platform: `_scrape_google_maps`,
`_scrape_facebook`, `_scrape_trustpilot`, `_scrape_instagram`. Facebook page scraping needs a
Bright Data token and degrades silently without one; keyword mentions still work through Apify.

`classification_service.py` classifies each review for sentiment, theme and complaint category,
and filters advertising.

`analytics.py` computes every figure: sentiment splits per platform, rating distribution, complaint
frequencies, reply rate, momentum between periods, and the rating-against-sentiment mismatch. All
in Python.

`social_report_service.generate_detailed_social_report` builds the prompt from those statistics,
asks the model for prose, then grounds the answer: channels no source covers are dropped, and each
finding is quantified by looking its echoed label back up. An invented label is cleared rather than
force-fitted, so a badge never contradicts the sentence beside it.

The report chatbot injects the computed statistics rather than retrieving
(`social_chat.report_to_context`).

### Files

| File | Contents |
|---|---|
| `services/scraping/job_service.py` | Job creation, the background task, status |
| `services/scraping/scraping_service.py` | Per-platform collection |
| `services/scraping/classification_service.py` | Per-review classification, ad filtering |
| `services/scraping/analytics.py` | `build_evidence` and every computed figure |
| `services/scraping/social_report_service.py` | Prompt, grounding, quantification |
| `services/scraping/social_chat.py` | `report_to_context`, the assistant |
| `services/scraping/manual_analysis_parser.py` | The consultant workbook |
| `services/scraping/findings.py` | Structured findings for the issue log |
| `frontend/src/features/social/hub.tsx` | Setup, job polling, dashboard |
| `frontend/src/features/social/report-view.tsx` | The report |
| `frontend/src/features/social/charts.tsx` | The figures |
| `frontend/src/features/social/excel.ts` | The workbook export |

### Where to change what

| Task | File |
|---|---|
| Add a platform | `scraping_service.py`, then `analytics.py` for its figures |
| Change a computed statistic | `analytics.py` |
| Change the report's wording | `social_report_service._report_prompt` |
| Change how findings are quantified | `social_report_service._quantify_from_labels` |
| Change a chart | `features/social/charts.tsx` |
| Change chart colours | `features/social/colors.ts` |
| Change the workbook | `features/social/excel.ts` |

## Issue log

Consolidates the findings of the other four modules into one prioritised register, marks where
sources disagree, and exports to Excel.

### The path through the code

`POST /issue-log` creates a job. `resolve.resolve_selections` turns the chosen analyses into
source references, and `collector.collect_findings` reads each one through its module's finding
extractor, checking access per source.

`sources.py` converts each analysis into chunks the model can read. `pipeline.generate_issues`
runs a model pass per chunk, then `normalise` canonicalises keys, resolves the taxonomy, removes
exact duplicates and verifies evidence. A finding whose dimension is not in the taxonomy is
dropped rather than guessed at.

`fragments.merge_fragments` merges issues quoting the same evidence, using union-find over
quote overlap. Grouping never crosses a chunk or a client. It refuses to shrink a run by more than
20 percent, and refuses to merge a group larger than the cap, because a correct rule does not find
five issues in one sentence.

`correlate.py` finds where sources disagree, `recommend.py` writes recommendations, and
`export.py` produces the workbook.

### Files

| File | Contents |
|---|---|
| `services/issue_log/job_service.py` | The run, stage by stage |
| `services/issue_log/resolve.py` | Selections to source references |
| `services/issue_log/collector.py` | `collect_findings`, per-module extraction with access checks |
| `services/issue_log/sources.py` | Analyses to chunks |
| `services/issue_log/pipeline.py` | `generate_issues`, `normalise` |
| `services/issue_log/taxonomy.py` | The strategic dimensions and sub-categories |
| `services/issue_log/fragments.py` | Merging and the anti-collapse floor |
| `services/issue_log/correlate.py` | Conflicts between sources |
| `services/issue_log/recommend.py` | Recommendations |
| `services/issue_log/verify.py` | Evidence checks, judgement-word detection |
| `services/issue_log/export.py` | The workbook |
| `services/issue_log/prompts.py` | Prompt text |
| `frontend/src/features/issue-log/page.tsx` | Dashboard, builder, job polling |
| `frontend/src/features/issue-log/result-view.tsx` | Issues, conflicts, recommendations |
| `frontend/src/features/issue-log/issue-card.tsx` | One finding, editable |

### Where to change what

| Task | File |
|---|---|
| Change the taxonomy | `taxonomy.py` |
| Change what a module contributes | that module's `findings.py`, then `sources.py` |
| Change how issues merge | `fragments.py` |
| Change the workbook | `export.py` (`ISSUE_COLUMNS`) |
| Change a prompt | `prompts.py` |

## Projects

A project is a layer over the five modules, not a sixth. It holds the pipeline for one engagement,
owns the results attached to it, and carries its members. Modules run identically with or without
one open.

`project_service.py` owns projects, members, steps and artifacts. An artifact is `(kind, ref_id)`,
which is why `ref_id` is a string: assessments and guides are integer primary keys, desk sessions
are hex ids and social reports are filenames.

On the frontend, `ActiveProjectContext` holds the open project so it survives launching a module,
and `lib/use-project-artifacts.ts` provides what is attached. Completing a module attaches its
result and advances the step.

| File | Contents |
|---|---|
| `services/projects/project_service.py` | Projects, members, steps, artifacts |
| `api/routes/projects.py` | Endpoints, including shares |
| `frontend/src/context/ActiveProjectContext.tsx` | The open project, attach, step status |
| `frontend/src/features/projects/hub.tsx` | The services page |
| `frontend/src/features/projects/pipeline.tsx` | Steps and attached results |
| `frontend/src/features/projects/step-nav.tsx` | The band modules show while a project is open |
| `frontend/src/lib/analysis-kinds.ts` | The four kinds and their labels |

# Part 3: Reference

## Database

35 tables. The schema is defined by numbered SQL in `backend/migrations/`, not by the models: a
model edited without a matching migration exists in no real database. `seed.py` applies them in
order and records what has run, so it is safe to repeat.

| Group | Tables |
|---|---|
| Identity | `users`, `invites`, `refresh_tokens`, `password_reset_tokens` |
| Projects | `projects`, `project_members`, `project_steps`, `project_artifacts`, `analysis_shares` |
| Assessment | `assessments`, `assessment_answers`, `assessment_scores`, `assessment_axis_memory`, `assessment_insights`, `assessment_recipients`, `assessment_idempotency`, `assessment_website_audits`, `recommendation_outputs` |
| Interviews | `interview_guides` |
| Social | `scraping_jobs` (request and result as JSONB) |
| Issue log | `issue_logs` |
| Reference data | `sectors`, `company_sizes`, `regions`, `axes`, `capabilities`, `maturity_levels`, `capability_maturity_rubrics`, `capability_recommendations`, `capability_quick_win_templates`, `axis_maturity_content`, `companies`, `company_sector_detections`, `company_size_detections` |
| Observability | `llm_calls` |

## Configuration

`backend/.env.example` documents every variable. What degrades without each:

| Variable | Without it |
|---|---|
| `DATABASE_URL` | Startup fails |
| `JWT_SECRET` | Startup fails unless `APP_ENV=development`, where an insecure fallback is used |
| `MISTRAL_API_KEY` | The application runs; every generative feature logs an error and returns nothing |
| `LANGSEARCH_API_KEY` | Reports generate without the competitor benchmark |
| `APIFY_API_TOKEN` | Social listening collects nothing |
| `BRIGHTDATA_API_TOKEN` | Facebook page scraping returns nothing; keyword mentions still work |
| `GEMINI_API_KEYS` | Images in documents are not described; text extraction is unaffected |
| `OPENROUTER_API_KEY` | No fallback when Gemini is rate limited |
| `SMTP_*` | Invites and client links must be copied manually instead of emailed |
| `STORAGE_BACKEND` | Defaults to local disk |
| `RAG_EMBED_BACKEND` | Defaults to the local model; lexical fallback if unavailable |

## API surface

All under `/api/v1`.

| Prefix | Router |
|---|---|
| `/auth` | `routes/auth.py` |
| `/assessments` | `routes/assessments.py`, including interview guides |
| `/respondent` | `routes/respondent.py`, the client link path |
| `/client` | `routes/client.py` |
| `/scraping` | `routes/scraping.py` |
| `/desk-research` | `routes/desk_research.py` |
| `/issue-log` | `routes/issue_log.py` |
| `/projects`, `/shares` | `routes/projects.py` |
| `/admin`, `/admin/reference`, `/admin/analytics` | `routes/admin_*.py` |
| `/reference` | `routes/reference.py` |

## Tests

564 tests in `backend/tests/`. `conftest.py` neutralises the environment before any application
module is imported and aborts the run if the configuration still resembles production. Do not add
a test that builds its own settings outside it.

Two groups are structural rather than example-based, and both fail the build when a new endpoint
forgets something. `test_admin_authorization.py` walks FastAPI's resolved dependency tree and
asserts that every `/admin` route resolves `require_admin`, and that every route taking a resource
id consults an ownership check somewhere. `test_storage_path_safety.py` asserts that a key built
from a URL parameter cannot leave its storage prefix.

47 frontend tests run under Vitest (`npm run test`, included in `npm run verify`). They cover the
auth client's refresh-on-401 and its promise never to persist the access token, the reload memory,
the shared analysis-kind labels, and the assessment hub's extracted hooks. The rest of the React
code is covered by type checking, the brand palette check and a production build.
