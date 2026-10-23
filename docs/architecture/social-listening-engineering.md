# Social Listening — Engineering Decisions

A code-and-rationale companion to [social-listening-pipeline.md](social-listening-pipeline.md)
(which covers *what* the module does). This document records the *why* behind the implementation —
the trade-offs suitable to cite in the report.

Code: `backend/app/services/scraping/` · Routes: `backend/app/api/routes/scraping.py` ·
Model: `backend/app/db/models/scraping_job.py`.

## Design forces

Four constraints shape almost every non-obvious decision:

1. **Latency** — a full run (3 Apify actors + Bright Data + ~5 Mistral calls) takes up to ~8 minutes,
   longer than reverse-proxy connection limits (nginx/ALB ≈ 60s, Azure App Service ≈ 230s).
2. **Provider flakiness** — third-party scrapers rate-limit, time out, and return transient 5xx
   *after the run is already billed*.
3. **Noisy input** — multilingual text (French, Arabic MSA, Tunisian Derja, Arabizi, mixed), spam
   (job ads, giveaways), and same-named businesses in other geographies.
4. **Deliverable-grade numbers** — every statistic must be defensible and reproducible; it cannot
   vary with LLM non-determinism.

---

## Decision 1 — Background job (answers force 1)

`POST /scraping/run` returns `202` with a `job_id`; the browser polls `GET /scraping/jobs/{id}`.
The `scraping_jobs` row is the unit of durability. (`job_service.py`)

- **Row committed before the task starts** (`create_job`) so an early failure has somewhere to report.
- **Task detached** via `asyncio.create_task`, with a **strong reference held in a module-level set**
  (`_running_tasks`) and discarded on completion — because asyncio holds only weak references and a
  bare task can be garbage-collected mid-run.
- **Concurrency cap** `_MAX_CONCURRENT_JOBS = 2` (semaphore): each run holds three actor runs plus
  several LLM calls; unbounded parallelism would exhaust provider rate limits and memory.
- **Progress written on a fresh short-lived session** (`_update` opens its own `SessionLocal`): the
  request's session is gone, and holding one open for 8 minutes would pin a pooled connection.
- **Archiving happens inside the task** (`_archive_run`), not on poll, so closing the tab still saves
  the run; archiving failures are logged and swallowed and never demote a succeeded scrape.
- **Restart self-heal** (`reap_stale_jobs`, called at startup): tasks live in memory, so a
  deploy/crash orphans in-flight jobs; any `pending`/`running` row is marked `failed` with an
  actionable message so the UI never polls a job that can't finish.

---

## Decision 2 — Isolated-failure fan-out (answers force 2)

`run_full_scrape` scrapes four platforms concurrently with
`asyncio.gather(..., return_exceptions=True)`; each scraper catches its own errors and returns a
`PlatformResult(status = success | empty | error)` rather than throwing. One dead platform greys out
one card; it never 500s the run.

- **Retry only transient statuses** — `_request_with_retry` retries `{408,425,429,500,502,503,504}`
  with exponential backoff (2s/4s/8s); a `401`/`404` fails immediately (retrying wastes time).
- **Poll resilience** — during actor polling, a failed *status* poll is retried (growing backoff)
  rather than abandoning the run, because the actor keeps running on the provider side and the work
  is already billed.
- **Per-page isolation (Facebook)** — `_scrape_facebook_single_page` swallows page-level errors (bad
  URL, 404, no posts) so other pages continue, but re-raises account-fatal errors ("Customer is not
  active").
- **Credential redaction** — `_redact()` strips tokens from any string that may be logged, stored, or
  shown (httpx embeds the URL in error text, which is persisted to the job row and report JSON);
  auth also travels in a `Bearer` header, not a query parameter.
- **Input hygiene before counting** — `_is_customer_feedback` / `_is_relevant_comment` /
  `_is_meaningful_instagram_comment` drop spam and non-feedback (AR+FR keyword lists);
  `_location_matches` filters same-named businesses in other countries (a brand-name search is
  global; geography is the only discriminator). Reviewer identities are not collected
  (`personalData: False`) for GDPR/INPDP data minimisation.
- **Star-only reviews retained** — reviews with a rating but no text skip the classifier yet still
  count toward the rating distribution (dropping them once collapsed 468 raw items to 196 and made
  the star histogram rest on a fraction of the data).

---

## Decision 3 — "LLM labels, Python counts" (answers force 4)

The classifier's only job is per-review labelling (sentiment / themes / complaint_category /
is_advertisement). **Every statistic is computed in Python** (`analytics.py`,
`_build_summary`), so quoted numbers cannot drift with the model. (`classification_service.py`)

- **Bounded sample** — `_MAX_REVIEWS_TO_CLASSIFY = 150` = one concurrency wave (`_MAX_CONCURRENCY=5`
  × `_CHUNK_SIZE=30`). Headline sentiment and main complaint dimensions are stable below this; a
  second wave would spend calls sharpening an unread long tail. The rating histogram uses *all*
  reviews regardless — the cap bounds only the semantic layer.
- **Fair sampling** — `_select_balanced_sample` round-robins across channels, so a quiet channel is
  not starved by a busy one and the logic holds for any number of platforms.
- **Chunk-local indices** — a returned label's `index` is resolved against the exact chunk serialised
  into that prompt, so a label can never attach to the wrong review. A failed chunk is caught and
  left unclassified; damage is contained to ≤30 reviews.
- **Two vocabularies, opposite strategies:**
  - `complaint_category` → **closed list, snapped at classification time** (`_snap_complaint` onto
    nine universal CX dimensions; exact fold-match → token-overlap → "Other"). An open complaint
    vocabulary fragments into synonyms ("service nul"/"service médiocre") that share no tokens and
    can never be merged afterwards, understating the ranked problems.
  - `themes` → **open vocabulary, reconciled after the fact** (`canonicalize_themes` merges variants
    by token-subset once all chunks return; dominant spelling wins). Chunks are independent LLM calls
    that never see each other, so "Réseau"/"Qualité du réseau" must be merged post-hoc.
  - *Principle:* reconcile an open vocabulary only where you can see all of it at once; otherwise
    constrain it up front.
- **Ad filtering** — items flagged `is_advertisement` are removed before any aggregation.

---

## Decision 4 — Honesty-first analytics (answers force 4)

`analytics.py` is pure arithmetic and repeatedly chooses to render nothing over something
misleading. The same `ReportEvidence` object (`build_evidence`) is both quoted as fact and fed into
the report-writing prompt, so the narrative is grounded in real distributions.

- **Theme noise floor** — `_MIN_THEME_SHARE_PCT = 3%` (keep at least the top 3 in a small corpus).
- **Trend guardrails** — `_TREND_MIN_SAMPLE = 10`, `_TREND_MIN_POINTS = 3`. Monthly and quarterly
  series are both built; the better-covered wins; buckets below the sample floor emit `null` (a gap,
  not a confident point); a section renders only at ≥50% coverage. Rationale recorded in code: a
  telco with 232 reviews still averaged ~7/month, which would swing a monthly line between 33% and
  100% on samples of three.
- **Momentum by halves** — `compute_topic_momentum` compares each complaint category's share between
  an earlier and a recent half (≥20 classified reviews each); two solid samples beat many noisy
  points. "Other" is excluded (no actionable movement).
- **Reply rate carries its base** — weighted by review count and returned with the base it rests on,
  so 0% on 8 reviews is not shown as if it covered 200.
- **Rating vs. sentiment check** — counts how often stars and written sentiment disagree, exposing
  sarcasm as a hard number.

---

## Storage

`scraping_jobs` stores `request` and `result` as **JSONB** in Postgres — durable, backed up,
reproducible. The report is **also** written to a `scraped_data/*.json` file, and the list/read
endpoints still read those files. This is redundant with `scraping_jobs.result` and is known storage
debt: the data already lives in Postgres; the read path has not yet been switched over. See
[storage-and-production-plan.md](storage-and-production-plan.md).

## Cross-cutting

- Ownership scoping (`owner_id`, `access.py`) on list/read/delete; path-traversal guard
  (`_resolve_report_path`) on the file-backed endpoints. See
  [auth-projects-and-sharing.md](auth-projects-and-sharing.md).
- The report chatbot (`social_chat.py`) uses the shared agentic engine with KPI injection (no vector
  search) — the report's computed evidence is the context.
