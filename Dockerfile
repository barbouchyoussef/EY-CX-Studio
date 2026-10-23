# syntax=docker/dockerfile:1
# One image that builds the React frontend and serves it from the FastAPI backend (same origin,
# so the SameSite=Strict refresh cookie works and there's no CORS). Deployed as a single service.

# ── Stage 1: build the React frontend ──────────────────────────────
FROM node:20-slim AS frontend
WORKDIR /fe
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
# Same-origin API: the built app calls /api/v1 on whatever host serves it.
ENV VITE_API_BASE_URL=/api/v1
RUN npm run build          # -> /fe/dist

# ── Stage 2: Python backend (also serves the built frontend) ───────
FROM python:3.12-slim AS backend
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app/backend

# System libraries: PDF rendering (poppler), image/vision libs (docling/PIL), OCR incl. Arabic.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libglib2.0-0 libgl1 poppler-utils \
        tesseract-ocr tesseract-ocr-ara \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./
RUN pip install -r requirements.txt

# ── Optionally pre-download the ML model weights into the image ───────────────
# Left to themselves, docling, EasyOCR and sentence-transformers fetch ~1.3 GB of weights on
# FIRST USE, into the container's writable layer. The VM's startup script recreates the
# container on every boot, so that download repeats after each restart and the first document
# upload pays for all of it -- a one-page PDF waits as long as a hundred-page one.
#
# Baking them in makes every restart warm and removes a runtime dependency on Hugging Face
# being reachable, at the cost of ~2 GB of image (2.9 GB -> 5.0 GB). That is a slow push on a
# home connection, so it is OFF by default and enabled deliberately:
#
#     docker build --build-arg BAKE_MODELS=1 -t <image> .
#
# Turn it on for a long-lived deployment; leave it off for quick iteration.
ARG BAKE_MODELS=0
COPY backend/scripts/bake_models.py /tmp/bake_models.py
RUN if [ "$BAKE_MODELS" = "1" ]; then python /tmp/bake_models.py; fi && rm -f /tmp/bake_models.py

COPY backend/ ./
# Place the built frontend where app/main.py serves it from.
COPY --from=frontend /fe/dist ./app/static/frontend

# Railway injects $PORT; default to 8000 for local `docker run`.
ENV PORT=8000
CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
