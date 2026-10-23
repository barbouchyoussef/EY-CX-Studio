# UX Specification: EY CX Studio

## 1. UX Goal

EY CX Studio should feel like a focused internal consulting workspace: clear, professional, structured, and efficient. Consultants should be able to move from client context to analysis to deliverable without losing track of evidence or project status.

## 2. Primary User Journeys

### Consultant Journey

1. Sign in.
2. Open or create a project.
3. Choose a module.
4. Complete analysis workflow.
5. Review generated output.
6. Attach output to project.
7. Generate issue log or export deliverables.

### Client Respondent Journey

1. Open passwordless assessment link.
2. Answer guided questions.
3. Complete assessment without seeing consultant-only data.

### Admin Journey

1. Sign in as admin.
2. Manage users and reference data.
3. Review analytics and system usage.
4. Update framework content when required.

## 3. UX Principles

- Keep workflows linear where the user is completing a task.
- Keep dashboards scannable where the user is reviewing outputs.
- Make job progress visible for long-running work.
- Let users recover from refreshes or closed tabs during jobs.
- Use bilingual copy where modules support English and French.
- Keep generated content editable or reviewable before client use.

## 4. Module UX Requirements

| Module | UX Requirements |
|---|---|
| Projects | Show pipeline status, attached artifacts, and member context clearly. |
| Assessment | Keep conversation focused, show progress, and make final report easy to review. |
| Interview guide | Support setup, generation, editing, answer capture, export, and chat assistance. |
| Desk research | Make upload status, extraction progress, report output, and chat retrieval clear. |
| Social listening | Show job status, computed metrics, report narrative, charts, and export options. |
| Issue log | Make selected sources, generated issues, conflicts, recommendations, and export clear. |

## 5. Navigation Requirements

- Authenticated users land on the internal services/project area.
- Active project context should be visible while launching modules.
- Users should be able to return from modules to project context.
- Admin areas should remain clearly separate from consultant workflows.

## 6. Empty and Error States

- Empty dashboards should explain the next available action.
- Provider-missing states should be understandable without exposing secrets.
- Job failures should show status and allow retry where practical.
- Access-denied states should not leak private resource existence.

## 7. UX Acceptance Criteria

- A new consultant can identify the five modules from the main workspace.
- A consultant can complete one module without reading developer documentation.
- Long-running job status is visible.
- Generated outputs can be reviewed before export.
- Project artifacts are discoverable after attachment.
