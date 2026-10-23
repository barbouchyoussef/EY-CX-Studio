# Bug Triage: EY CX Studio

## 1. Purpose

Bug triage ensures defects are categorized, prioritized, assigned, and resolved according to product risk and release impact.

## 2. Severity Levels

| Severity | Definition | Examples |
|---|---|---|
| Critical | Blocks release or exposes sensitive data. | Auth bypass, data leak, app cannot start. |
| High | Breaks a core workflow. | Assessment cannot complete, issue log cannot generate. |
| Medium | Impacts important functionality with workaround. | Export formatting issue, one provider path fails. |
| Low | Minor usability, copy, or polish issue. | Typo, minor visual spacing, non-blocking warning. |

## 3. Priority Rules

Prioritize by:

1. Security and data exposure.
2. Release blockers.
3. Core workflow failures.
4. Data integrity issues.
5. High-frequency UX friction.
6. Cosmetic or documentation issues.

## 4. Triage Process

1. Confirm the issue is reproducible.
2. Identify affected module and user role.
3. Assign severity and priority.
4. Check whether it blocks current release.
5. Assign owner.
6. Define acceptance criteria.
7. Verify fix with targeted tests.
8. Update documentation if behavior changes.

## 5. Required Information

- Environment.
- User role.
- Steps to reproduce.
- Expected and actual result.
- Error logs or screenshots.
- Related job id, assessment id, project id, or report id where relevant.

## 6. Release Blocking Criteria

A bug blocks release if it:

- Allows unauthorized access.
- Corrupts persisted data.
- Prevents login.
- Prevents project creation.
- Prevents core module completion.
- Prevents deployment startup.
- Causes unreviewed client data leakage.
