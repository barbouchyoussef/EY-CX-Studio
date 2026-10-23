import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router

# Send app logs to stdout so the hosting platform (Render/Railway) captures them. Without this the
# services' logger.info/exception calls are invisible in the deploy logs. force=True overrides any
# handler uvicorn/gunicorn already installed on the root logger.
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    force=True,
)

# httpx logs every request at INFO, including the full URL. Gemini takes its API key as a query
# parameter, so that line writes a working credential into the log on every vision call --
# `docker logs` on the VM, readable by anyone who can reach it. The gemini_vlm logger truncates
# the key to eight characters for exactly this reason, which achieves nothing while the whole
# thing is printed two lines above. WARNING keeps the failures worth seeing and drops the
# per-request URLs.
logging.getLogger("httpx").setLevel(os.getenv("HTTPX_LOG_LEVEL", "WARNING").upper())

logger = logging.getLogger(__name__)

# In production the backend also serves the built React app (same origin, so the SameSite=Strict
# refresh cookie works and there's no CORS). The frontend build is copied here by the Dockerfile.
# Absent in local dev (Vite dev server + separate API) -> the block below simply doesn't mount.
_FRONTEND_DIST = Path(os.getenv("FRONTEND_DIST", "app/static/frontend"))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Close out scraping jobs orphaned by a previous process.

    Jobs run as in-process tasks, so a restart (including an autoreload in dev) leaves rows
    stuck at 'running' that no task will ever finish. Without this the UI polls them forever.
    """
    logger.info("CX Platform API starting up — logging is live.")
    try:
        from app.db.session import SessionLocal
        from app.services.scraping.job_service import reap_stale_jobs

        async with SessionLocal() as db:
            await reap_stale_jobs(db)
    except Exception:
        # Never block startup on housekeeping -- a database that is not up yet is not fatal here.
        logger.exception("Could not reap interrupted scraping jobs at startup")
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="CX Assessment API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix="/api/v1")

    # Serve the built frontend for every non-API path (only when a build is present).
    if _FRONTEND_DIST.is_dir():
        assets = _FRONTEND_DIST / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")
        index_html = _FRONTEND_DIST / "index.html"

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str) -> FileResponse:
            # The API is matched first (registered above); never let the SPA shadow it.
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="Not found")
            # Serve a real static file (favicon, logo, etc.) when it exists; else the SPA shell.
            candidate = _FRONTEND_DIST / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(index_html)

        logger.info("Serving frontend from %s", _FRONTEND_DIST.resolve())

    return app


app = create_app()
