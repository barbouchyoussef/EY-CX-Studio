# Adding a module

The platform is built from modules: the maturity assessment, interview guides, desk research,
social listening and the issue log are all the same shape. This is the order to build a sixth in,
and the list of places that already know how many there are.

Two things are worth knowing before starting.

The shared machinery needs no changes. A new module gets the model gateway, retrieval, storage,
authentication, project attachment and sharing by using them; none of them have a per-module
branch to extend.

Nothing here fails quietly. Every registration below is enforced by something — a closed
TypeScript union, a Pydantic literal, or a deny-by-default fallback. Miss one and the module is
rejected at the boundary or simply does not appear. The failure table at the end says which is
which, and it is the reason this checklist is worth following rather than memorising.

## 1. The database

Add one numbered SQL file to `backend/migrations/`. Take the next free number; the highest in use
is `056`. Numbers are not unique historically (`002` and `025` each appear twice) but do not add
to that.

`seed.py` applies migrations in order and records which have run, so it is safe to re-run. The
schema is defined by these files, not by the SQLAlchemy models: a model added without a migration
exists in no real database, and the application will raise an undefined-table error the first time
it touches it.

Then add the model under `backend/app/db/models/` and register it in that package's `__init__.py`,
alongside the 26 already there.

## 2. The service

`backend/app/services/<module>/` holds the work. Look at `issue_log/` for a module that reads from
others, or `desk_research/` for one that ingests files.

Two conventions apply to every service:

**Model calls go through the gateway.** Never call a provider directly. Wrap the work in
`llm_context` so the calls are attributed:

```python
with llm_context(feature="mymodule.generate", owner_id=user.id, ref_kind="my_analysis", ref_id=ref):
    ...
```

The `feature` string is what the cost dashboards group by. Skipping it is not an error, which is
why the `llm_calls` table currently holds 125 rows attributed to `unknown` — those call sites
predate the tag. Set it.

**Figures are computed in Python.** Pass computed statistics into the prompt and ask the model to
explain them. Never ask a model for a number that ends up in a report.

Add the repository under `backend/app/repositories/` and the request and response shapes under
`backend/app/schemas/`.

## 3. The API

Add `backend/app/api/routes/<module>.py` as an `APIRouter(prefix=...)`, then register it in
`backend/app/api/router.py` next to the 15 already there. Everything lands under `/api/v1`.

Every endpoint that reads or writes a record goes through `app/services/auth/access.py`. Do not
write an ownership check inside a route.

## 4. Register the analysis kind

This is the part that spans files. If the module produces something a consultant can save, share
and attach to a project, it is an *analysis kind* and eight places need to know about it.

| File | What to add |
|---|---|
| `backend/app/schemas/project.py` | The kind in the `ArtifactKind` literal |
| `backend/app/services/auth/access.py` | A branch in `owns_analysis`, and one in the file-backed resolver above it |
| `backend/app/services/issue_log/resolve.py` | The kind in `SUPPORTED_KINDS` |
| `backend/app/services/issue_log/sources.py` | A `chunks_from_<module>` function |
| `backend/app/services/issue_log/collector.py` | An entry in `_RESOLVERS` |
| `backend/app/services/issue_log/export.py` | How the source is labelled in the spreadsheet |
| `frontend/src/lib/projectsApi.ts` | The kind in the `AnalysisKind` union, and the step in `PROJECT_STEP_KEYS` if it joins the pipeline |
| `frontend/src/lib/analysis-kinds.ts` | Short and long labels, English and French |

The issue log entries are the ones people forget, because the module works perfectly without them.
Every source has a different shape, so consolidation cannot be generic: `sources.py` needs a
function that turns your module's output into chunks, and `collector.py` needs to know to call it.
Until both exist the module simply never contributes to an issue log.

`access.py` is a chain of `if kind == ...` rather than a registry. Two functions need the new
branch. It ends in `return False`, so a missing branch denies rather than allows.

## 5. The frontend

`frontend/src/features/<module>/` with an `index.ts` naming the single component the rest of the
application may import. Nothing outside the folder imports anything else from it.

Add the lazy import and the route in `src/App.tsx` — routing is `pathname.startsWith`, not
react-router — and a tile in the services hub under `src/features/projects/`.

Put user-facing strings in a `copy.ts` beside the components, keyed by language, rather than
inline in JSX. Colours come from the Tailwind brand tokens (`bg-ey-gold`, `text-ey-navy`); use
`src/lib/brand.ts` only where a class name cannot reach, such as a chart series.

## 6. Tests

`backend/tests/`. Model calls are stubbed, so no test spends money or depends on a provider.
`conftest.py` replaces the environment before any application module is imported and fails the run
outright if the configuration still resembles production.

Cover the access rules as well as the happy path. Two structural tests already do part of this
for you and will fail on a new endpoint that forgets: `test_admin_authorization.py` asserts that
every `/admin` route resolves `require_admin` and that every route taking a resource id consults
an ownership check, and `test_storage_path_safety.py` asserts that a key built from a URL
parameter cannot leave its prefix. `test_auth_security.py` covers the authentication primitives
underneath — bcrypt truncation, expired and tampered tokens, `alg:none` forgery.

Those prove a check exists, not that it is the right one. A test showing your new kind is visible
to its owner and refused to a stranger is still worth writing.

Frontend tests run under Vitest, in `*.test.ts` beside the code. Hooks are the cheap thing to
cover; whole hubs are not.

## 7. Documentation

- `docs/architecture/<module>.md`, one document for the module
- The module table and the cross-cutting list in `docs/architecture/README.md`
- A feature chapter in `DEEPDIVE.md`, and its tables in the Database section
- The modules table in `README.md`
- Any new environment variable in `backend/.env.example`

## What happens if you miss a step

| Missed | Result |
|---|---|
| `AnalysisKind` union | `tsc` fails; it is a closed union |
| `PROJECT_STEP_KEYS` | `tsc` fails; `StepKey` is derived from it with `as const` |
| `ArtifactKind` literal | Rejected by Pydantic at the API boundary |
| `access.py` branch | `owns_analysis` returns `False`, so the analysis is invisible to everyone including its owner |
| `_RESOLVERS` entry | The selection is reported as unresolvable in the issue log's `sources` |
| `llm_context` tag | Calls are recorded as `unknown` and drop out of per-feature cost reporting |
| A migration | Undefined-table error the first time the model is used |

Only the last two are quiet. The others stop the build or make the module conspicuously absent.

## Verify

```bash
cd backend  && python seed.py && python -m pytest
cd frontend && npm run verify && npm run lint
```
