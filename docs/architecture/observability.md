# LLM Observability Layer

A lightweight, self-hosted observability layer that records **every LLM API call** as a row in
Postgres, for cost / latency / error tracking and per-feature, per-user, per-object attribution.
Built to answer "what is the platform spending, and is it healthy?" — distinct from the *business*
analytics in `/admin/analytics` (maturity scores, pain points).

- **Capture:** `backend/app/services/llm/core/gateway.py` (`MistralGateway.chat_messages`)
- **Writer + cost + context:** `backend/app/services/observability/llm_metrics.py`
- **Model / table:** `backend/app/db/models/llm_call.py` · `migrations/051_create_llm_calls.sql`

## 1. How it works (capture → store → view)

```
every LLM call ──(gateway logs 1 row, best-effort)──▶ llm_calls (Postgres) ──▶ Metabase dashboard
```

- The gateway times each call and, on the way out (success **or** failure), calls `log_llm_call(...)`
  with the model, latency, and the provider `usage` block (token counts) that was previously
  discarded.
- `log_llm_call` is **fire-and-forget** (`asyncio.create_task`, strong-ref set to dodge the GC weak-
  reference trap) on **its own short-lived session**, wrapped in a swallow-all `try/except`. A
  logging failure — or a slow insert — never affects or slows the LLM call. Telemetry is optional;
  the product is not.
- **Context tags** (`feature`, `owner_id`, `ref_kind`, `ref_id`, `request_id`) ride on **contextvars**
  set once at a boundary and inherited by every LLM call underneath — including background tasks,
  because contextvars are copied into any `asyncio` task spawned within the context.

## 2. Data model — `llm_calls`

| Column | Meaning |
|---|---|
| `feature` | which operation made the call, e.g. `assessment.answer`, `social.classify` |
| `provider`, `model` | `mistral` / `moonshot` / …, and the exact model id |
| `ok`, `error` | success flag + truncated error (for error-rate charts) |
| `latency_ms` | wall-clock duration (measured with `time.monotonic`) |
| `prompt_tokens`, `completion_tokens`, `total_tokens` | from the provider `usage` block |
| `cost_usd` | `NUMERIC(12,6)` — estimated (never a float; money must not drift) |
| `owner_id` | who triggered it (`ON DELETE SET NULL` — telemetry outlives the user) |
| `ref_kind` + `ref_id` | domain object, e.g. `('assessment', '42')` — enables cost-per-object |
| `request_id` | groups all calls made within one user action |

## 3. Cost model — READ THIS

`cost_usd = tokens × price`, where price comes from `_PRICE_PER_MTOK` in `llm_metrics.py`
(USD per 1,000,000 tokens, input/output), matched by exact model id, then prefix, else a default.

> **The prices currently in the table are approximate placeholders, not verified figures.** Before
> trusting the cost numbers, replace them with the exact per-token prices from each provider's
> pricing page. The provider's billing dashboard is always ground truth; this column is a live
> *estimate* of it. `cost_usd` is `NULL` whenever the provider returned no usage (we never guess).

## 4. Coverage

**All four providers are instrumented:**
- **Mistral** (gateway) — assessment loop (`assessment.question` / `assessment.answer`, carrying the
  assessment id in `ref_id`; nested intent/coverage/memory calls inherit the tag), `social.classify`,
  `interview.chat`, `interview.insights`.
- **Moonshot/Kimi** — `interview.generate` (interview-guide generation).
- **Google Gemini** + **OpenRouter** — `desk.vlm` (desk-research image captioning).
- `owner_id` is set on every authenticated request (in `get_current_user`).

The writer auto-selects an **async** fire-and-forget insert inside an event loop, or a **synchronous**
psycopg2 insert for thread contexts (the VLM runs inside `asyncio.to_thread`). `mark_llm()` tags those
sync/threaded call sites. Any un-wrapped Mistral call still logs as `feature='unknown'`.

## 5. Where you view it, and who can

**Recommended: Metabase** (self-hosted, free) connects directly to Postgres; build the questions
below by pointing at `llm_calls`. View it either directly in Metabase (its own admin login) or
embedded in the app via the existing signed-JWT embed (`admin_analytics.metabase_embed`).

**Access control:** this data is admin-only. Gate any in-app observability route with
`require_admin`. Note the existing `/admin/analytics/*` endpoints currently have **no server-side
auth** (frontend-gated only) — a gap worth closing when this ships.

## 6. Metabase questions (ready-to-paste SQL)

**Cost per day**
```sql
SELECT date_trunc('day', created_at)::date AS day, ROUND(SUM(cost_usd), 4) AS cost_usd
FROM llm_calls GROUP BY 1 ORDER BY 1;
```

**Cost & volume per feature**
```sql
SELECT feature, COUNT(*) AS calls,
       ROUND(SUM(cost_usd), 4) AS cost_usd, SUM(total_tokens) AS tokens
FROM llm_calls GROUP BY 1 ORDER BY cost_usd DESC NULLS LAST;
```

**Error rate per feature**
```sql
SELECT feature, COUNT(*) AS calls,
       SUM(CASE WHEN NOT ok THEN 1 ELSE 0 END) AS errors,
       ROUND(100.0 * SUM(CASE WHEN NOT ok THEN 1 ELSE 0 END) / COUNT(*), 1) AS error_pct
FROM llm_calls GROUP BY 1 ORDER BY error_pct DESC;
```

**Latency (p50 / p95) per feature**
```sql
SELECT feature,
       ROUND(percentile_cont(0.50) WITHIN GROUP (ORDER BY latency_ms)) AS p50_ms,
       ROUND(percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)) AS p95_ms
FROM llm_calls WHERE latency_ms IS NOT NULL GROUP BY 1 ORDER BY p95_ms DESC;
```

**Cost per user**
```sql
SELECT COALESCE(u.full_name, 'unattributed') AS "user", COUNT(*) AS calls,
       ROUND(SUM(c.cost_usd), 4) AS cost_usd
FROM llm_calls c LEFT JOIN users u ON u.id = c.owner_id
GROUP BY 1 ORDER BY cost_usd DESC NULLS LAST;
```

**Cost per assessment** (top spenders)
```sql
SELECT ref_id AS assessment_id, COUNT(*) AS calls, ROUND(SUM(cost_usd), 4) AS cost_usd
FROM llm_calls WHERE ref_kind = 'assessment'
GROUP BY 1 ORDER BY cost_usd DESC NULLS LAST LIMIT 20;
```

## 7. Langfuse — trace inspection + evaluation

The **same gateway seam** also mirrors every call to **Langfuse** (`log_llm_call` →
`_emit_langfuse` in `llm_metrics.py`). This is the layer that stores the *actual prompt and
response text* (the Postgres row never does) and enables **evaluation** (scoring outputs). It is a
no-op unless `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST` are set.

- **SDK:** `langfuse` v2 (`.trace()` + `trace.generation()`), which Langfuse Cloud ingests fine.
- **Best-practice fields applied:** model, token usage, cost, input/output, a descriptive `name`
  (the feature), plus **`user_id`** (owner), **`session_id`** (`request_id` or the `ref_id`, e.g.
  the assessment id), and **`tags`** (`kind` + module).
- **Trace grouping:** an `llm_context` block opens one Langfuse trace (via a `_trace_id`
  contextvar); every LLM call inside the operation nests under it as a generation — so "one
  assessment answer → its 3 model calls" shows as a single trace, not three loose ones.
- **Safety:** wrapped so a Langfuse failure never affects the LLM call; short-lived scripts call
  `flush_langfuse()` (the long-running server flushes via the SDK's background thread).

**Division of labour:** Metabase = cost/health aggregates + domain attribution (from Postgres);
Langfuse = per-call trace inspection + evaluation. One seam feeds both.

> Privacy note: Langfuse receives full prompt/response text. Cloud is fine for testing; for
> production with real client data, self-host Langfuse (same code, different `LANGFUSE_HOST`) or add
> PII masking before send.

## 8. Follow-ups

1. Replace the placeholder prices with real figures.
2. Extend capture to the Moonshot call and the desk-research VLMs.
3. Gate the in-app observability view with `require_admin` (and fix the existing analytics gap).
4. (Phase 2/3) optional Langfuse for trace-tree UI + eval scoring; a weekly cost/error digest email;
   an offline eval harness on a golden set.
