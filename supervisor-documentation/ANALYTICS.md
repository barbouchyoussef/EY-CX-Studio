# Analytics: EY CX Studio

## 1. Analytics Purpose

Analytics help understand platform usage, module adoption, LLM cost, job reliability, and consultant workflow effectiveness.

## 2. Existing Analytics Sources

| Source | Purpose |
|---|---|
| `llm_calls` table | Tracks LLM usage, outcomes, and cost-related metadata. |
| Admin analytics routes | Expose administrative analytics views. |
| Job tables | Track scraping and issue-log job status and failures. |
| Project artifacts | Show module usage across projects. |
| Optional Langfuse | Traces prompt and response content when configured. |
| Optional Metabase | Dashboarding support through separate compose service. |

## 3. Key Metrics

### Product Usage

- Number of active users.
- Number of projects created.
- Module starts and completions.
- Artifacts attached per project.
- Export events where tracked.

### Operational Health

- Job success and failure rates.
- Average job duration.
- Provider error rates.
- LLM retry counts.
- Missing-configuration incidents.

### AI Usage

- LLM calls by feature.
- Token usage by feature.
- Failed LLM calls.
- Provider fallback usage.
- Average generation latency.

### Consulting Outcomes

- Completed assessments.
- Generated reports.
- Issue logs generated from multiple evidence sources.
- Manual edits or review comments where future tracking exists.

## 4. Data Governance

- Analytics must not expose client-sensitive content to unauthorized users.
- Prompt tracing must be approved before use with real client data.
- Usage analytics should aggregate where possible.
- Admin analytics should remain admin-only.

## 5. Future Analytics Enhancements

- Add explicit event tracking for key frontend actions.
- Add dashboard for module conversion funnels.
- Add provider health dashboard.
- Add release-quality dashboard showing tests, jobs, and errors.
- Add report-review metrics if an approval workflow is introduced.
