"""LLM observability — record every gateway call as a row in `llm_calls`.

Two design rules govern this module:

1. **A call's context (which feature, which user, which object) rides on contextvars**, set once
   at a request boundary. Individual call sites don't pass it; every LLM call made inside that
   context inherits it. contextvars are copied into any asyncio task spawned within the context,
   so background work (classification chunks, the next-question prefetch) keeps the right tags.

2. **Writing is best-effort and fire-and-forget on its own short-lived session.** A logging
   failure, or a slow insert, must never affect — or slow — the LLM call it describes. Same
   instinct as `job_service._update`: telemetry is optional; the product is not.
"""

from __future__ import annotations

import asyncio
import contextvars
import logging
import uuid
from contextlib import contextmanager

from app.core.config import get_settings
from app.db.models.llm_call import LLMCall
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------------------------
# 1. Context — what the current LLM call belongs to
# --------------------------------------------------------------------------------------------
_feature: contextvars.ContextVar[str] = contextvars.ContextVar("llm_feature", default="unknown")
_kind: contextvars.ContextVar[str | None] = contextvars.ContextVar("llm_kind", default=None)
_owner_id: contextvars.ContextVar[int | None] = contextvars.ContextVar("llm_owner_id", default=None)
_ref_kind: contextvars.ContextVar[str | None] = contextvars.ContextVar("llm_ref_kind", default=None)
_ref_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("llm_ref_id", default=None)
_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("llm_request_id", default=None)
_trace_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("llm_trace_id", default=None)


@contextmanager
def llm_context(
    *,
    feature: str | None = None,
    kind: str | None = None,
    owner_id: int | None = None,
    ref_kind: str | None = None,
    ref_id: str | int | None = None,
    request_id: str | None = None,
):
    """Tag every LLM call made inside this block, then restore the previous tags on exit.

    Usage:
        with llm_context(feature="social.classify", kind="run", owner_id=user.id):
            await classify_reviews(...)          # every gateway call inside is tagged
    """
    tokens = []
    if feature is not None:
        tokens.append((_feature, _feature.set(feature)))
    if kind is not None:
        tokens.append((_kind, _kind.set(kind)))
    if owner_id is not None:
        tokens.append((_owner_id, _owner_id.set(owner_id)))
    if ref_kind is not None:
        tokens.append((_ref_kind, _ref_kind.set(ref_kind)))
    if ref_id is not None:
        tokens.append((_ref_id, _ref_id.set(str(ref_id))))
    if request_id is not None:
        tokens.append((_request_id, _request_id.set(request_id)))
    # Group every LLM call inside this operation under ONE Langfuse trace. Nested llm_context
    # blocks inherit the trace already set, so an operation's sub-calls stay in the same trace.
    if feature is not None and _trace_id.get() is None:
        tokens.append((_trace_id, _trace_id.set(uuid.uuid4().hex)))
    try:
        yield
    finally:
        for var, token in reversed(tokens):
            var.reset(token)


def bind_owner(owner_id: int | None) -> None:
    """Attribute every LLM call in the current request context to a user.

    Set once at the auth boundary (get_current_user). Unlike `llm_context`, it does not restore
    a previous value: each request runs in its own context, so there is nothing to leak into.
    """
    _owner_id.set(owner_id)


# --------------------------------------------------------------------------------------------
# 2. Cost model — USD per 1,000,000 tokens, as (input_price, output_price)
#    APPROXIMATE. Update these from each provider's pricing page. Matched by exact model id,
#    then by prefix, else the default. Kept in code (not config) because they change rarely and
#    are easy to eyeball here next to the calc that uses them.
# --------------------------------------------------------------------------------------------
_PRICE_PER_MTOK: dict[str, tuple[float, float]] = {
    # Mistral list prices, checked against mistral.ai/pricing/api on 2026-09-01.
    "mistral-large": (0.50, 1.50),   # Large 3
    "mistral-medium": (1.50, 7.50),  # Medium 3.5 <- mistral-medium-latest
    "mistral-small": (0.15, 0.60),   # Small 4    <- mistral-small-latest
    "ministral": (0.10, 0.10),       # Ministral 3 3B; 8B and 14B are 0.15 and 0.20
    "moonshot-v1": (0.14, 0.28),     # Kimi/Moonshot — RMB-priced (~¥1/¥2); USD is FX-dependent
    "kimi": (0.14, 0.28),
    # Gemini Flash-Lite list prices. Actual spend is $0 while inside the free tier, which is
    # where this project has stayed; these are what it would cost on the paid tier.
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-3.1-flash-lite": (0.25, 1.50),
    "gemini": (0.30, 2.50),          # unrecognised Gemini → price as the dearer Flash-Lite
    "nvidia/nemotron": (0.0, 0.0),   # OpenRouter ":free" model → no cost
}
_DEFAULT_PRICE = (1.00, 3.00)


def _price_for(model: str | None) -> tuple[float, float]:
    if not model:
        return _DEFAULT_PRICE
    m = model.lower()
    if m in _PRICE_PER_MTOK:
        return _PRICE_PER_MTOK[m]
    for prefix, price in _PRICE_PER_MTOK.items():
        if m.startswith(prefix):
            return price
    return _DEFAULT_PRICE


def estimate_cost_usd(
    model: str | None, prompt_tokens: int | None, completion_tokens: int | None
) -> float | None:
    """Tokens × price. None when the provider returned no usage (we can't guess a cost)."""
    if prompt_tokens is None and completion_tokens is None:
        return None
    in_price, out_price = _price_for(model)
    pt = prompt_tokens or 0
    ct = completion_tokens or 0
    return round((pt * in_price + ct * out_price) / 1_000_000, 6)


# --------------------------------------------------------------------------------------------
# 2b. Langfuse (optional) — send the same calls, WITH prompt/response text, to Langfuse for
#     trace inspection + evaluation. Disabled (no-op) unless LANGFUSE_* keys are configured.
#     This is the one place that sees the actual prompt/response; the Postgres row never does.
# --------------------------------------------------------------------------------------------
_langfuse_client = None
_langfuse_init_done = False


def _get_langfuse():
    global _langfuse_client, _langfuse_init_done
    if _langfuse_init_done:
        return _langfuse_client
    _langfuse_init_done = True
    s = get_settings()
    if not (s.langfuse_public_key and s.langfuse_secret_key):
        return None  # not configured -> Langfuse simply off
    try:
        from langfuse import Langfuse

        _langfuse_client = Langfuse(
            public_key=s.langfuse_public_key,
            secret_key=s.langfuse_secret_key,
            host=s.langfuse_host,
        )
    except Exception:
        logger.exception("could not initialise Langfuse client (continuing without it)")
        _langfuse_client = None
    return _langfuse_client


def _emit_langfuse(
    *, feature, kind, provider, model, ok, error, latency_ms,
    prompt_tokens, completion_tokens, input_messages, output_text,
) -> None:
    client = _get_langfuse()
    if client is None:
        return
    try:
        owner = _owner_id.get()
        module = (feature or "unknown").split(".")[0]
        # Trace = the user action (best-practice fields: user_id, session_id, tags). Calling it
        # with the same id upserts, so an operation's several generations share one trace.
        trace = client.trace(
            id=_trace_id.get() or uuid.uuid4().hex,
            name=feature,
            user_id=str(owner) if owner is not None else None,
            session_id=_request_id.get() or _ref_id.get(),
            tags=[t for t in (kind, module) if t] or None,
            metadata={"ref_kind": _ref_kind.get(), "ref_id": _ref_id.get()},
        )
        # Generation = the actual model call, nested under the trace.
        trace.generation(
            name=feature,
            model=model,
            input=input_messages,
            output=output_text,
            usage={"input": prompt_tokens, "output": completion_tokens, "unit": "TOKENS"},
            level="ERROR" if not ok else "DEFAULT",
            status_message=error or None,
            metadata={"kind": kind, "provider": provider, "latency_ms": latency_ms},
        )
    except Exception:
        logger.exception("langfuse emit failed (ignored; the LLM call is unaffected)")


def flush_langfuse() -> None:
    """For short-lived scripts: force queued events to send before the process exits.
    (A long-running server flushes automatically via Langfuse's background thread.)"""
    if _langfuse_client is not None:
        try:
            _langfuse_client.flush()
        except Exception:
            pass


# --------------------------------------------------------------------------------------------
# 3. The writer — best-effort, fire-and-forget
# --------------------------------------------------------------------------------------------
# Strong refs to in-flight log writes: asyncio holds only weak references to bare tasks, so
# without this a log write could be garbage-collected before it commits. (Same trap the
# scraping job runner guards against.)
_log_tasks: set[asyncio.Task] = set()
_sync_engine = None


def _get_sync_engine():
    """A lazily-built SYNC engine (psycopg2) for logging from no-event-loop contexts —
    e.g. the desk-research VLM, which runs inside asyncio.to_thread."""
    global _sync_engine
    if _sync_engine is None:
        from sqlalchemy import create_engine

        url = get_settings().database_url.replace("+asyncpg", "")  # -> psycopg2 sync URL
        _sync_engine = create_engine(url, pool_size=1, max_overflow=2, pool_pre_ping=True)
    return _sync_engine


async def _record_async(row: dict) -> None:
    """Insert one row on a fresh short-lived async session. Never raises."""
    try:
        async with SessionLocal() as db:
            db.add(LLMCall(**row))
            await db.commit()
    except Exception:
        logger.exception("llm_calls insert failed (the LLM call itself is unaffected)")


def _record_sync(row: dict) -> None:
    """Insert one row synchronously (sync callers with no event loop). Never raises."""
    try:
        with _get_sync_engine().begin() as conn:
            conn.execute(LLMCall.__table__.insert().values(**row))
    except Exception:
        logger.exception("llm_calls sync insert failed (the LLM call itself is unaffected)")


def mark_llm(*, feature: str | None = None, kind: str | None = None,
             ref_kind: str | None = None, ref_id: str | int | None = None) -> None:
    """Set LLM tags for the CURRENT context without restoring — for sync/threaded call sites
    (e.g. the desk-research VLM) that run in their own copied context. Opens a trace once."""
    if feature is not None:
        _feature.set(feature)
    if kind is not None:
        _kind.set(kind)
    if ref_kind is not None:
        _ref_kind.set(ref_kind)
    if ref_id is not None:
        _ref_id.set(str(ref_id))
    if _trace_id.get() is None:
        _trace_id.set(uuid.uuid4().hex)


def log_llm_call(
    *,
    provider: str,
    model: str | None,
    ok: bool,
    error: str | None = None,
    latency_ms: int | None = None,
    usage: dict | None = None,
    input_messages: list | None = None,
    output_text: str | None = None,
) -> None:
    """Record one gateway call. Reads token counts from the provider's `usage` block and the
    feature/owner/ref tags from the current context. Fire-and-forget: it schedules the DB write
    and returns immediately, adding no latency to the LLM call.

    `input_messages`/`output_text` are the actual prompt/response — used only for Langfuse (the
    Postgres row stores numbers, never the text)."""
    usage = usage or {}
    pt = usage.get("prompt_tokens")
    ct = usage.get("completion_tokens")
    tt = usage.get("total_tokens") or ((pt or 0) + (ct or 0)) or None

    # Mirror to Langfuse (no-op unless configured). Synchronous but non-blocking: it only
    # enqueues an event in memory; the SDK's background thread ships it.
    _emit_langfuse(
        feature=_feature.get(), kind=_kind.get(), provider=provider, model=model,
        ok=ok, error=error, latency_ms=latency_ms, prompt_tokens=pt, completion_tokens=ct,
        input_messages=input_messages, output_text=output_text,
    )
    row = {
        "feature": _feature.get(), "kind": _kind.get(), "provider": provider,
        "model": model[:80] if model else None, "ok": ok,
        "error": str(error)[:300] if error else None, "latency_ms": latency_ms,
        "prompt_tokens": pt, "completion_tokens": ct, "total_tokens": tt,
        "cost_usd": estimate_cost_usd(model, pt, ct),
        "owner_id": _owner_id.get(), "ref_kind": _ref_kind.get(),
        "ref_id": _ref_id.get(), "request_id": _request_id.get(),
    }
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        _record_sync(row)          # sync caller (e.g. VLM in a thread) — write inline
        return
    task = asyncio.create_task(_record_async(row))   # async caller — fire-and-forget
    _log_tasks.add(task)
    task.add_done_callback(_log_tasks.discard)
