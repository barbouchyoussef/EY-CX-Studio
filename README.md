<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-f5c542?style=for-the-badge&logo=opensourceinitiative&logoColor=white" alt="MIT License"/></a>&nbsp;
  <a href="backend/requirements.txt"><img src="https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.12"/></a>&nbsp;
  <a href="https://fastapi.tiangolo.com/"><img src="https://img.shields.io/badge/Framework-FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI"/></a>&nbsp;
  <a href="https://react.dev/"><img src="https://img.shields.io/badge/Frontend-React_19-61DAFB?style=for-the-badge&logo=react&logoColor=black" alt="React 19"/></a>&nbsp;
  <a href="https://vite.dev/"><img src="https://img.shields.io/badge/Build-Vite-646CFF?style=for-the-badge&logo=vite&logoColor=white" alt="Vite"/></a>
</p>

# EY CX Studio

EY CX Studio is an internal platform for running customer experience consulting engagements. It
provides five analysis modules that a consultant can use independently, and a project layer that
groups them so the work done for one client is tracked in one place.

The interface and the generated deliverables are bilingual (English and French). Access is
invite only: every route requires a signed in account, apart from the passwordless link a
consultant sends to a client so that the client can answer an assessment directly.

## Modules

| Module | Purpose |
|---|---|
| Maturity assessment | A guided conversation that scores customer experience maturity on the Manage, Analyze and Improve axes against the framework's rubrics, then produces a report with quick wins, a recommendation timeline, and a benchmark of sector leaders built from web evidence. |
| Interview guide | Generates a stakeholder interview guide, either from a completed assessment or from scratch. The guide is editable, answers are captured against each question, and an assistant cross references those answers with the assessment to flag disagreements. |
| Desk research | Accepts client documents (PDF, DOCX, PPTX, XLSX, images) and produces a structured report. A chatbot answers questions over both the documents and the report it generated. |
| Social listening | Collects public reviews and posts, classifies each one for sentiment, theme and complaint category, then reports on the aggregate. Every figure in the report is computed in Python; the model writes only the prose around it. |
| Issue log | Consolidates the findings of the other modules into one prioritised list of issues, with the conflicts between sources made explicit, and exports it as a spreadsheet. |

### Projects

A project is not a sixth module. It is a layer over the five: it holds the pipeline for one client
engagement, results attach to it as each module produces them, and members can be added so a
colleague sees the same work. The modules do not depend on it and each runs the same way with or
without a project open.

## Architecture

The backend is a FastAPI application over PostgreSQL, organised by feature under
`backend/app/services/`. Each feature owns its services; shared concerns (the language model
gateway, retrieval, storage, authentication) sit beside them and are used by all.

Two decisions are worth stating up front because they shape the rest:

**Every language model call goes through one gateway** (`app/services/llm/core/gateway.py`). That
is what applies the retry policy and what records usage into the `llm_calls` table, so a feature
that built its own HTTP request would be invisible to cost reporting.

**Numbers are computed in Python, never by a model.** Reports pass computed statistics into the
prompt and ask the model to explain them. This is why a report is reproducible across runs.

The frontend is React 19 with TypeScript, Vite and Tailwind CSS v4. It is organised the same way:
`src/features/` holds one folder per module, each behind an `index.ts` that names the single
component the rest of the application may import. `src/components/ui/` holds only what more than
one module uses.

## Repository layout

```
backend/
  app/
    api/routes/        HTTP endpoints, grouped by feature
    services/          the features, plus shared llm/, rag/, auth/, storage
    repositories/      database access
    db/models/         SQLAlchemy mappings
    schemas/           request and response shapes
  migrations/          numbered SQL, applied in order by seed.py
  tests/
frontend/
  src/
    features/          one folder per module and for projects, each with an index.ts
    components/ui/     shared components only
    lib/               API client, shared hooks, copy tables, brand palette
docs/
  architecture/        one document per feature
```

## Running it locally

### Prerequisites

- Python 3.12
- Node.js 20
- PostgreSQL 13 or later, running locally

Note that `docker-compose.yml` in the repository root does not start the application database. It
runs Metabase and a separate PostgreSQL instance for it, used for the analytics dashboards. The
application database has to be created separately.

### 1. Database

Create an empty database, for example:

```bash
createdb cx_assessment
```

### 2. Backend

```bash
cd backend
python -m venv .venv
# Windows:      .venv\Scripts\Activate.ps1
# macOS, Linux: source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
```

Edit `.env` and set `DATABASE_URL`. It is the only variable the application refuses to start
without.

`JWT_SECRET` is optional while `APP_ENV` is `development`, where the application falls back to a
known insecure value and says so. It is required for any other value of `APP_ENV`, and startup
fails without it.

Apply the schema and the reference data. `seed.py` runs the numbered SQL migrations in order and
records which have already been applied, so it is safe to run again:

```bash
python seed.py
```

Create the first account. There is no open sign up, so this is how anyone gets in:

```bash
ADMIN_EMAIL=you@example.com ADMIN_PASSWORD='a strong passphrase' python -m app.scripts.create_admin
```

Start the API:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 3. Frontend

```bash
cd ../frontend
npm install
npm run dev
```

Open `http://localhost:5173` and sign in with the account created above. From the services page you
can open a module directly or create a project first.

### First run notes

Retrieval uses a local embedding model (`multilingual-e5-small`) that downloads on first use, about
470 MB. If `sentence-transformers` is not installed the chatbots fall back to keyword retrieval
automatically, so the application still runs.

Document extraction downloads model weights on first use as well. The first upload is therefore
noticeably slower than later ones.

## Configuration

All backend configuration is read from environment variables. `backend/.env.example` documents
every one of them.

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `JWT_SECRET` | Outside development | Signs access tokens. A development fallback exists; any other environment requires it |
| `MISTRAL_API_KEY` | For anything generative | The main chat model. Without it the application starts and the modules load, but every feature that writes text logs an error and returns nothing |
| `LANGSEARCH_API_KEY` | For benchmarks | Web search behind the competitor benchmark |
| `APIFY_API_TOKEN` | For social listening | Review and post collection |
| `GEMINI_API_KEYS` | For images | Vision captioning of images in uploaded documents |
| `OPENROUTER_API_KEY` | Optional | Fallback provider when Gemini is unavailable |
| `SMTP_*` | For invites | Sending invitations and client assessment links |

The frontend reads `VITE_API_BASE_URL`, which defaults to the local API.

Runtime data written by the application (`scraped_data/`, `desk_research_data/`, `rag_data/`,
`interview_chat_data/`) is ignored by git, as is `.env`.

## Tests and checks

Backend:

```bash
cd backend
python -m pytest
```

There are 564 tests and they pass. They run against a neutralised configuration:
`tests/conftest.py` replaces the environment before any application module is imported and fails
the run outright if the configuration still points at anything resembling production.

Frontend:

```bash
cd frontend
npm run verify     # type check, brand palette check, production build
npm run lint
```

`npm run check:brand`, included in `verify`, asserts that the brand colours defined in
`src/index.css` match those in `src/lib/brand.ts`. The palette is written in both places because
CSS custom properties cannot be read from JavaScript without a DOM, and the check is what keeps
the two from drifting.

## Deployment

The `Dockerfile` builds both halves into one image: the frontend is built with Node and its
output is copied into the Python image, which serves the API and the built frontend from the same
process. The container listens on `$PORT`, defaulting to 8000.

```bash
docker build -t cx-studio .
docker run --env-file deploy.env -p 8000:8000 cx-studio
```

One deployment detail is easy to get wrong: `docker run --env-file` is not a shell. It does not
strip quotes or trailing comments, so a value written as `MISTRAL_API_KEY="abc"` is sent with the
quotation marks included and every model call fails authentication. Values in the env file must be
unquoted.

## Documentation

`DEEPDIVE.md` is the reference for the codebase itself. It covers each feature in turn: what it
does, which files implement it, how a request travels through them, and where the decisions that
are not obvious from the code are recorded. Start there when you need to change something rather
than run it.

`docs/architecture/` holds one document per feature, written while each was built, covering the
engineering decisions in more depth than this file.


