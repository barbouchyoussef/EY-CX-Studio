# Product Specification: EY CX Studio

## 1. Product Behavior

EY CX Studio behaves as a secure, authenticated workspace for CX consulting modules. Consultants sign in, choose or create a project, run one or more analysis modules, attach outputs to the project, and generate client-ready artifacts for review.

All consultant-facing modules require authentication. The only non-account flow is the respondent assessment flow, which is accessed through a scoped token.

## 2. Global Rules

- Users must be authenticated for all consultant and admin workflows.
- Admin workflows require admin privileges.
- Client respondent links expose only the assessment tied to their token.
- Generated numbers must come from deterministic application logic, not LLM invention.
- LLM-generated narrative must be grounded in computed statistics, uploaded content, or recorded answers.
- English and French copy must be supported where module copy is user-facing.
- Runtime data and secrets must not be committed to git.

## 3. Project Rules

- A project represents one client engagement.
- A project can have an owner and members.
- Modules can run independently, with or without an active project.
- When a module output is attached to a project, it becomes a project artifact.
- Artifacts are identified by kind and reference id because different modules use different id formats.
- Project members can view project artifacts through access-control checks.

## 4. Maturity Assessment Rules

- An assessment belongs to a company and optionally to a project.
- The assessment evaluates capabilities under the Manage, Analyze, and Improve axes.
- The system tracks current axis, pending question, state version, language, conversation stage, and scoring state.
- A repeated answer submission with the same idempotency key must not score twice.
- Low-quality, confused, or resume messages are handled as conversation control events and must not create false evidence.
- The final report uses persisted scores, evidence, quick wins, recommendations, and benchmark data.
- Competitor benchmark data is optional when search credentials are unavailable.

## 5. Interview Guide Rules

- A guide can be generated from a completed assessment or from standalone company context.
- The guide is editable after generation.
- Answers are captured against individual questions.
- Chat assistance must reason over the current guide state, including unsaved frontend edits when supplied.
- Generated insights compare interview answers against assessment evidence when available.

## 6. Desk Research Rules

- Supported inputs include PDF, DOCX, PPTX, XLSX, and images.
- Digital PDFs should use a native text extraction path when possible.
- Thin extraction results should trigger fallback extraction or OCR.
- Extracted content is indexed for retrieval.
- The generated report and uploaded documents are both available to the chatbot.
- If semantic embeddings are unavailable, retrieval falls back to lexical matching.

## 7. Social Listening Rules

- Social listening runs as a background job.
- The frontend polls job status instead of waiting on one long HTTP request.
- Each collected item is classified for sentiment, theme, and complaint category.
- Aggregate statistics are computed by backend logic.
- The report narrative explains the computed metrics.
- Manual analysis workbooks can supplement or replace scraped data.

## 8. Issue Log Rules

- Issue-log generation runs as a background job.
- Selected source analyses are resolved and access-checked before processing.
- Findings are converted into source chunks and normalized against the issue taxonomy.
- Invalid taxonomy dimensions must be dropped rather than guessed.
- Related findings can be merged only when evidence overlap supports it.
- Conflicts between sources must be explicit.
- The final register can be exported to Excel.

## 9. Edge Cases

| Scenario | Expected Behavior |
|---|---|
| Missing `DATABASE_URL` | Backend startup fails. |
| Missing LLM key | App can start, but generative features fail gracefully or return no generated content. |
| Missing scraping token | Social scraping returns no external results; manual upload remains available. |
| Missing embedding model | Chatbot uses lexical retrieval. |
| Duplicate assessment answer request | Stored idempotent response is returned. |
| Expired respondent token | Respondent flow rejects access. |
| Stale background job after restart | Startup housekeeping marks or reaps stale jobs. |
| User lacks ownership or project access | API denies resource access. |

## 10. Acceptance Criteria

- A consultant can sign in and access the services dashboard.
- A consultant can create a project and attach module outputs.
- A maturity assessment can progress through questions and produce a final report.
- A respondent link allows only the target assessment interaction.
- A document upload can produce a desk research report and chat context.
- A social listening run can be started, polled, and displayed when credentials are configured.
- An issue log can consolidate selected module outputs and export a workbook.
- Admin endpoints are protected by admin authorization.
- Backend tests and frontend verification commands pass before release.
