# Deployment: EY CX Studio

## 1. Deployment Model

The application can be deployed as a single container. The Dockerfile builds the React frontend, copies the built assets into the Python backend image, and serves both the API and frontend from FastAPI.

## 2. Build Command

```bash
docker build -t cx-studio .
```

## 3. Run Command

```bash
docker run --env-file deploy.env -p 8000:8000 cx-studio
```

## 4. Required Services

- PostgreSQL application database.
- Optional object storage for production runtime artifacts.
- Optional SMTP provider.
- Optional LLM, scraping, search, and observability providers depending on enabled features.

## 5. Environment File Rules

- `docker run --env-file` does not strip quotes.
- Values must be unquoted.
- Do not include inline comments after values.
- Never commit production env files.

Example:

```text
MISTRAL_API_KEY=abc123
```

Not:

```text
MISTRAL_API_KEY="abc123"
```

## 6. Deployment Steps

1. Provision PostgreSQL.
2. Create production environment file.
3. Build Docker image.
4. Run migrations with `python seed.py`.
5. Create first admin account.
6. Start application container.
7. Confirm `/api/v1/health` responds.
8. Confirm frontend loads.
9. Confirm login and refresh-cookie behavior.
10. Run smoke tests for selected modules.

## 7. Production Considerations

- Use HTTPS.
- Set secure cookie options.
- Configure a strong `JWT_SECRET`.
- Configure object storage if local disk is not persistent.
- Confirm provider data-processing policies.
- Monitor logs for job failures and provider errors.
- Back up PostgreSQL and object storage.

## 8. Rollback Plan

- Keep the previous image available.
- Back up database before applying new migrations.
- If deployment fails before migration, redeploy previous image.
- If migration has run, confirm whether rollback SQL is required before downgrading.
- Preserve logs for failure analysis.
