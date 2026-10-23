"""RAG engine orchestration: build an index, retrieve, and answer with citations.

This is the module-agnostic core. A product module supplies (a) chunks under its namespace and
(b) an ``llm_fn`` for answering; everything else -- retrieval, context assembly, source list --
is shared. That is what lets the same chatbot front and flow be reused across modules with only
the data source changing.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Awaitable, Callable

from app.schemas.rag import RagChunk, RetrievedChunk
from app.services.rag.store import (  # re-export for callers
    build_index,
    delete_index,
    has_index,
    query_index,
)

logger = logging.getLogger(__name__)

__all__ = [
    "build_index", "delete_index", "has_index", "query_index",
    "answer_query", "agentic_answer", "rag_context_source", "RagChunk",
]

# An async function: (system_prompt, user_prompt) -> answer text.
LlmFn = Callable[[str, str], Awaitable[str]]

# A context source gathers grounding for a query. It receives the raw user query and the
# planner's rewritten queries, and returns (context_text, sources). This is the ONE piece that
# differs per module: desk research retrieves document chunks; social injects computed KPIs and
# optionally retrieves verbatims. Everything else in the agentic loop is shared.
ContextSource = Callable[[str, list[str]], Awaitable[tuple[str, list[str]]]]


def _citation(source_name: str, page: int | None) -> str:
    return f"{source_name}" + (f", p{page}" if page else "")


async def answer_query(
    namespace: str,
    query: str,
    llm_fn: LlmFn,
    *,
    system_prompt: str,
    k: int = 6,
    empty_message: str = "No documents are available in this session to answer from.",
) -> dict:
    """Retrieve the top-k chunks for ``query`` and have ``llm_fn`` answer grounded in them.

    Returns ``{"answer", "sources", "retrieved_count"}``. Sources are de-duplicated citations
    ("filename, p3") in retrieval order.
    """
    retrieved = query_index(namespace, query, k=k)
    if not retrieved:
        return {"answer": empty_message, "sources": [], "retrieved_count": 0}

    context_lines: list[str] = []
    sources: list[str] = []
    for r in retrieved:
        c = r.chunk
        cite = _citation(c.source_name, c.page)
        sources.append(cite)
        context_lines.append(f"--- [Source: {cite}] ---\n{c.text}")

    user_prompt = (
        "Use ONLY the context below to answer. If the answer is not in the context, say so.\n\n"
        "Context from the session's documents:\n\n"
        + "\n\n".join(context_lines)
        + f"\n\nQuestion: {query}"
    )
    answer = await llm_fn(system_prompt, user_prompt)

    return {
        "answer": answer,
        "sources": list(dict.fromkeys(sources)),  # de-dupe, keep order
        "retrieved_count": len(retrieved),
    }


# --------------------------------------------------------------------------- #
#  Agentic RAG                                                                 #
# --------------------------------------------------------------------------- #

_PLANNER_SYSTEM = """You are the retrieval planner for a document assistant.
Given the conversation and the user's latest message, decide whether answering requires searching
the user's uploaded documents, and if so, what to search for.

Reply with ONLY a JSON object, no prose:
{"needs_search": true|false, "queries": ["focused search query", "..."]}

Rules:
- needs_search=false for greetings, thanks, small talk, or questions about you/your capabilities.
- needs_search=true for anything about the documents' content, data, figures, or findings.
- When true, provide 1-3 focused search queries. Resolve pronouns/ellipsis using the conversation
  (e.g. if the user says "and in 2025?", expand it into a self-contained query).
- Keep queries in the language of the documents/question."""


def _history_text(history: list[dict] | None, max_turns: int = 6) -> str:
    if not history:
        return "(no prior messages)"
    recent = history[-max_turns:]
    lines = []
    for m in recent:
        role = "User" if str(m.get("role")) == "user" else "Assistant"
        text = str(m.get("text") or m.get("content") or "").strip()
        if text:
            lines.append(f"{role}: {text}")
    return "\n".join(lines) if lines else "(no prior messages)"


def _extract_json(text: str) -> dict | None:
    """Pull the first JSON object out of a model reply (handles ```json fences / stray prose)."""
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


async def _plan(query: str, history: list[dict] | None, llm_fn: LlmFn) -> tuple[bool, list[str]]:
    """Decide whether to search and produce search queries. Fails safe to searching once."""
    planner_user = (
        f"Conversation so far:\n{_history_text(history)}\n\n"
        f"Latest user message: {query}\n\n"
        "Return the JSON decision now."
    )
    try:
        raw = await llm_fn(_PLANNER_SYSTEM, planner_user)
        data = _extract_json(raw)
        if isinstance(data, dict) and "needs_search" in data:
            needs = bool(data["needs_search"])
            queries = [str(q).strip() for q in (data.get("queries") or []) if str(q).strip()]
            if needs and not queries:
                queries = [query]
            return needs, queries[:3]
    except Exception:
        logger.warning("Retrieval planner failed; defaulting to a single search.", exc_info=True)
    return True, [query]  # safe default: search with the raw question


def _multi_query_retrieve(namespace: str, queries: list[str], k: int) -> list[RetrievedChunk]:
    """Retrieve for several queries and merge, keeping each chunk's best score."""
    best: dict[str, RetrievedChunk] = {}
    per_query_k = max(3, k // max(1, len(queries)) + 2)
    for q in queries:
        for rc in query_index(namespace, q, k=per_query_k):
            cid = rc.chunk.chunk_id
            if cid not in best or rc.score > best[cid].score:
                best[cid] = rc
    merged = sorted(best.values(), key=lambda r: r.score, reverse=True)
    return merged[:k]


def rag_context_source(
    namespace: str,
    k: int = 8,
    *,
    header: str = "Relevant excerpts from the documents:",
) -> ContextSource:
    """Build a context source that retrieves document chunks by semantic similarity.

    This is the desk-research (and verbatim) context source. It runs the planner's queries
    against the namespace's vector index and formats the hits with inline citations.
    """
    async def _source(query: str, planned_queries: list[str]) -> tuple[str, list[str]]:
        if not has_index(namespace):
            return "", []
        queries = planned_queries or [query]
        retrieved = _multi_query_retrieve(namespace, queries, k=k)
        if not retrieved:
            return "", []
        lines: list[str] = []
        sources: list[str] = []
        for r in retrieved:
            c = r.chunk
            cite = _citation(c.source_name, c.page)
            sources.append(cite)
            lines.append(f"--- [Source: {cite}] ---\n{c.text}")
        return f"{header}\n\n" + "\n\n".join(lines), list(dict.fromkeys(sources))

    return _source


async def agentic_answer(
    query: str,
    llm_fn: LlmFn,
    *,
    answer_system_prompt: str,
    context_source: ContextSource,
    history: list[dict] | None = None,
    preamble: str = "",
    plan: bool = True,
) -> dict:
    """Shared agentic loop: plan → gather context (pluggable) → answer with role + history.

    The model first decides whether external context is even needed, so greetings/meta questions
    are answered directly and content questions are grounded. ``context_source`` is the ONLY
    module-specific piece: swap RAG retrieval (desk research) for KPI injection (social) without
    touching this loop. ``preamble`` (e.g. the document list, or "a report exists") is always
    available so the model can answer overview questions without gathering context.
    """
    needs_context, queries = (True, [query])
    if plan:
        needs_context, queries = await _plan(query, history, llm_fn)

    context_block, sources = "", []
    if needs_context and context_source is not None:
        try:
            context_block, sources = await context_source(query, queries)
        except Exception:
            logger.warning("Context source failed; answering without it.", exc_info=True)

    body = context_block or "(No supporting context was gathered for this message.)"
    answer_user = (
        (f"{preamble}\n\n" if preamble else "")
        + f"{body}\n\n"
        + f"Conversation so far:\n{_history_text(history)}\n\n"
        + f"User's latest message: {query}"
    )
    answer = await llm_fn(answer_system_prompt, answer_user)

    return {
        "answer": answer,
        "sources": list(dict.fromkeys(sources)),
        "retrieved_count": len(sources),
        "used_context": bool(context_block),
    }
