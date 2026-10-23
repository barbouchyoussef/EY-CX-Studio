# Configuration: EY CX Studio

## 1. Configuration Source

Backend configuration is read from environment variables. The template is `backend/.env.example`.

Frontend configuration is read from Vite environment variables, primarily `VITE_API_BASE_URL`.

## 2. Required Backend Variables

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL connection string. |
| `JWT_SECRET` | Outside development | Signs access tokens. |
| `APP_ENV` | Recommended | Controls development fallback behavior. |

## 3. Feature Provider Variables

| Variable | Purpose |
|---|---|
| `MISTRAL_API_KEY` | Main generative model provider. |
| `MOONSHOT_API_KEY` | Optional chat provider. |
| `GEMINI_API_KEYS` | Text failover and image captioning. |
| `OPENROUTER_API_KEY` | Optional vision fallback. |
| `LANGSEARCH_API_KEY` | Benchmark search evidence. |
| `APIFY_API_TOKEN` | Social listening scraping. |
| `BRIGHTDATA_API_TOKEN` | Facebook page/comment scraping. |
| `SMTP_*` | Invites and password reset emails. |
| `LANGFUSE_*` | Optional LLM tracing. |

## 4. Storage Configuration

| Variable | Purpose |
|---|---|
| `STORAGE_BACKEND` | Selects disk or production storage backend. |
| Storage provider variables | Required when using object storage. |

If unset in development, local disk storage is used.

## 5. RAG and Document Configuration

| Variable | Purpose |
|---|---|
| `RAG_EMBED_BACKEND` | Selects local embeddings or lexical fallback. |
| `RAG_EMBED_MODEL` | Embedding model name. |
| `RAG_MIN_SCORE` | Minimum similarity threshold. |
| `DESK_OCR_LANGS` | OCR language configuration. |

## 6. Cookie Configuration

| Variable | Purpose |
|---|---|
| `COOKIE_SECURE` | Should be true in HTTPS production. |
| `COOKIE_SAMESITE` | Recommended strict same-site behavior. |
| `COOKIE_DOMAIN` | Optional domain scoping. |

## 7. Configuration Rules

- Do not commit `.env`.
- Keep `backend/.env.example` updated when new variables are introduced.
- Production env files must not include quotes around values for Docker `--env-file`.
- Missing optional provider keys should degrade gracefully where possible.
- Missing required core variables should fail fast.
