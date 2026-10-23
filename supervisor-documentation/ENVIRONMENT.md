# Environment: EY CX Studio

## 1. Local Development Environment

Required:

- Python 3.12
- Node.js 20
- PostgreSQL 13 or later
- Git

Recommended:

- Isolated Python virtual environment.
- Local `.env` copied from `backend/.env.example`.
- Separate test database or disposable local database.

## 2. Backend Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python seed.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

## 4. Runtime Data

Runtime data can be written under ignored directories such as:

- `scraped_data/`
- `desk_research_data/`
- `rag_data/`
- `interview_chat_data/`

These should not be committed.

## 5. First-Run Notes

- Local embeddings may download a model on first use.
- Document processing can download model weights on first upload.
- Missing `sentence-transformers` causes RAG fallback to lexical retrieval.
- Missing provider keys means generative or scraping features may not produce results.

## 6. Production Environment

Production should provide:

- PostgreSQL.
- Persistent storage backend.
- HTTPS.
- Strong JWT secret.
- Secure cookie settings.
- Provider API keys as approved.
- SMTP configuration if invites and resets should be emailed.
