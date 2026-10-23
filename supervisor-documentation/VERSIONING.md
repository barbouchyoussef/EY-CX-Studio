# Versioning: EY CX Studio

## 1. Versioning Goal

Versioning should make releases traceable and understandable for supervisors, developers, and users.

## 2. Recommended Scheme

Use semantic versioning:

```text
MAJOR.MINOR.PATCH
```

Examples:

- `1.0.0` for first approved internal release.
- `1.1.0` for backward-compatible feature additions.
- `1.1.1` for bug fixes.
- `2.0.0` for breaking architecture or workflow changes.

## 3. Version Rules

| Change Type | Version Impact |
|---|---|
| Critical bug fix | Patch |
| Documentation-only change | Patch or no release version, depending on process |
| New module feature | Minor |
| New provider integration | Minor |
| Database migration with backward-compatible app behavior | Minor |
| Breaking API or workflow change | Major |
| Authentication model change | Major |

## 4. Release Notes

Each release should record:

- Version number.
- Date.
- Summary.
- Added features.
- Fixed issues.
- Database migrations.
- Configuration changes.
- Known risks.

## 5. Database Versioning

- Migration files are the database version history.
- A release should identify the latest migration included.
- Rollback planning must consider migration reversibility.

## 6. Documentation Versioning

- Supervisor documentation should be updated when release scope changes.
- `CHECKPOINT.md` should reflect current status before review.
- `DECISIONS.md` should record major architectural changes.
