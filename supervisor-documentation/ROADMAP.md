# Roadmap: EY CX Studio

## Now: Documentation and Stabilization

- Complete governance documentation requested by project leadership.
- Verify backend and frontend checks.
- Review `.env.example` against actual runtime requirements.
- Confirm local setup instructions are reproducible.
- Triage any known failing tests, lint issues, or provider gaps.

## Next: Pilot Readiness

- Run one end-to-end pilot project with representative data.
- Validate maturity assessment scoring and final report quality.
- Validate desk research extraction across common file types.
- Validate social listening with configured provider tokens.
- Validate issue-log generation from multiple module outputs.
- Review generated deliverables with consultants before client use.

## Release 1: Internal Consulting Use

- Support invite-only consultant access.
- Support project workspaces and artifact attachment.
- Support the five core analysis modules.
- Support bilingual consultant-facing workflows where implemented.
- Provide exports for reports, guides, social listening, and issue logs.
- Provide admin workflows for users, reference data, capability content, and analytics.

## Release 2: Reliability and Operations

- Improve job monitoring and retry visibility.
- Add clearer provider health diagnostics.
- Add richer audit trails for generated deliverables.
- Expand observability dashboards over `llm_calls` and job execution.
- Define retention policy for uploaded files and generated artifacts.
- Harden deployment documentation for the selected production host.

## Release 3: Product Expansion

- Expand social platform coverage where provider access is approved.
- Add more sector-specific benchmark candidate sets.
- Improve collaborative review workflows for issue logs and reports.
- Add richer project status dashboards.
- Improve report export styling and client-ready packaging.

## Future Considerations

- Dedicated vector database if retrieval corpus size grows significantly.
- Formal workflow approvals for client-facing deliverables.
- Fine-grained roles beyond admin and consultant.
- Integration with document repositories or engagement-management systems.
- Automated regression datasets for generated report quality.

## Out of Scope for Current Roadmap

- Public self-service signup.
- Full CRM functionality.
- Replacing consultant review of generated reports.
- Unapproved scraping of restricted or private channels.
