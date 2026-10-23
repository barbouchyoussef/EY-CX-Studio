# Risk Register: EY CX Studio

| ID | Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|---|
| R-001 | LLM-generated text may contain unsupported claims. | Medium | High | Compute numbers in Python, ground prompts in evidence, require consultant review. | Product and engineering |
| R-002 | Provider API keys may be missing or invalid. | High | Medium | Document configuration, degrade gracefully, add provider health checks. | Engineering |
| R-003 | Social platforms may change scraping access. | Medium | High | Support manual analysis uploads and provider abstraction. | Product |
| R-004 | Uploaded document extraction may fail on poor-quality scans. | Medium | Medium | Use native extraction, Docling, OCR, and fallback paths. | Engineering |
| R-005 | Client data may be exposed through tracing providers. | Low | High | Approve Langfuse/tracing use before real client data. | Security owner |
| R-006 | Database migrations may not match ORM models. | Medium | High | Require migrations for schema changes and run tests. | Engineering |
| R-007 | Long-running jobs may be interrupted by process restarts. | Medium | Medium | Reap stale jobs and persist job status. | Engineering |
| R-008 | Docker env-file formatting may break provider credentials. | Medium | Medium | Document unquoted env-file values and validate deployment. | DevOps |
| R-009 | Frontend accessibility gaps may affect users. | Medium | Medium | Add accessibility review before wider release. | Product and frontend |
| R-010 | Large ML dependencies may increase deployment size and cold start time. | Medium | Medium | Use CPU wheels and document first-run downloads. | Engineering |
| R-011 | Unauthorized access bugs may expose analyses. | Low | High | Central access checks and security tests. | Engineering |
| R-012 | Project scope may expand beyond internship timeline. | Medium | Medium | Maintain roadmap, release plan, and checkpoint documents. | Project team |
