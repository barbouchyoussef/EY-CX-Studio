# Security: EY CX Studio

## 1. Security Goals

- Protect client analysis data.
- Prevent unauthorized access to consultant and admin workflows.
- Scope client respondent access to a single assessment.
- Avoid leaking provider credentials or uploaded content.
- Preserve traceability for generated content and model usage.

## 2. Authentication Model

- Access is invite-only.
- Admin creates or invites users.
- Users authenticate with email and password.
- Access tokens are short-lived and stored in browser memory.
- Refresh tokens are stored in `HttpOnly` cookies and rotate.
- Password reset tokens are hashed and expire.

## 3. Authorization Model

Access to analysis data is granted when:

- The user owns the record.
- The record is shared with the user.
- The record belongs to a project where the user is a member.
- The user is an admin for admin-only workflows.

Authorization logic is centralized in the backend access service.

## 4. Respondent Security

- Client respondents do not receive full user accounts.
- Respondent tokens are scoped to exactly one assessment.
- Raw tokens are not stored.
- Tokens expire and can be revoked.
- Respondent endpoints must never accept only a guessed assessment id.

## 5. Data Protection

- Secrets must be stored in environment variables.
- `.env` files must not be committed.
- Uploaded documents and generated artifacts must use the storage service.
- Provider API keys must not appear in logs.
- Runtime data directories are ignored by git.

## 6. Admin Security

- Admin endpoints must require admin dependencies.
- Admin workflows include users, reference data, capability content, and analytics.
- Tests should verify admin dependency enforcement when routes are added.

## 7. LLM and Provider Security

- All LLM calls go through the shared gateway.
- `llm_calls` stores usage metadata.
- Langfuse tracing may receive prompt and response content when configured.
- Production use should review whether client data is allowed to leave the platform through tracing or provider calls.

## 8. Common Risks

| Risk | Mitigation |
|---|---|
| Token theft from browser storage | Access token kept in memory; refresh token in `HttpOnly` cookie. |
| Unauthorized resource access | Central ownership, share, and project membership checks. |
| Client token overreach | Respondent tokens scoped to one assessment. |
| Secret leakage in logs | Avoid full provider URLs and credentials in logs. |
| Path traversal in storage | Storage path-safety tests and storage abstraction. |
| LLM hallucination | Compute numbers in Python and ground narrative in evidence. |

## 9. Release Security Checklist

- No `.env` or secrets committed.
- `JWT_SECRET` configured outside development.
- Production cookies use secure settings.
- Admin route tests pass.
- Storage path-safety tests pass.
- Provider logging does not expose credentials.
- Langfuse or other tracing is approved for client content.
