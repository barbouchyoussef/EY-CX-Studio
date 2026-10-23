# Social Listening — Scrape → Classify → Analyze → Report

Code: `backend/app/services/scraping/`. Routes: `backend/app/api/routes/scraping.py`.
UI: `frontend/src/features/social/hub.tsx` + `features/social/report-view.tsx`.

Pulls public customer feedback for a brand across channels, AI-classifies each item, computes
deterministic analytics, and renders an executive report with charts. There are two input sources:
**automatic scraping** and a **manual analysis workbook** (a consultant-supplied Excel of posts).

## 1. Scraping (async job)

Sources: **Google Maps, Facebook, Trustpilot**. Scraping runs as a background **job** (the request
returns a `job_id`; the frontend polls, and a reload/closed tab rejoins the run via a persisted
`activeJobId`). Each collected item is a `ScrapedReview` (`app/schemas/scraping.py`):

```
platform, author, text, rating, date, url, source, classification
```

`source` distinguishes, for Facebook, the brand's **official page** (`page`) from **keyword-search**
mentions (`keyword`) — "owned vs earned" conversation.

## 2. Classification (per review, LLM)

`classification_service.classify_reviews(reviews, brand_name)`:

- **Balanced sample** across platforms (`_select_balanced_sample`) → chunked → classified
  concurrently (bounded) via the Mistral gateway. Star-only reviews (no text) skip the model but
  still count toward the rating distribution.
- Each review gets a `ReviewClassification`: **sentiment** (pos/neu/neg), **confidence**,
  **themes** (short reused labels), **complaint_category** (snapped to a fixed dimension list), and
  **`is_advertisement`**.
- The prompt handles **multilingual + Tunisian/North-African Derja + Arabizi**, sarcasm/irony
  ("Bravo TT 👏 10h sans internet" → negative), and mixed praise-then-complaint.
- **Ad filtering:** reviews flagged `is_advertisement` (promo posts, giveaways, affiliate spam — but
  *not* a real complaint that merely mentions a product) are **dropped before any statistic is
  computed**, so ads never pollute reviews, topics, or sentiment.
- `canonicalize_themes` reconciles the open theme vocabulary across chunks so counts aren't split by
  two spellings of one subject.

## 3. Analytics (deterministic, `analytics.py`)

Computed from the classified set so the narrative is written against real distributions:

| Function | Produces |
|---|---|
| `compute_sentiment` / `compute_platform_sentiment` | overall & per-channel pos/neu/neg |
| `compute_rating_distribution` | 1–5★ histogram (incl. per-platform) |
| `compute_theme_frequencies` | topics by volume + negative share |
| `compute_complaint_frequencies` | complaint categories (fixed dimensions) |
| `compute_reply_rate` | share of reviews the brand replied to |
| `compute_rating_sentiment_check` | reviews whose stars contradict their text |
| `compute_trend` | negativity / avg-rating **and pos/neu/neg share** over time (month/quarter), only when the sample honestly supports a time axis |
| `compute_topic_momentum` | which complaint categories are rising / falling (two-half comparison) |

Trend/momentum deliberately return nothing on thin samples — a shift measured on a handful of
reviews is noise, not a movement.

## 4. Report

`social_report_service.py` assembles the report: an LLM narrative grounded in the computed evidence
(sentiment, complaints, channels, trends, recommendations) + the structured aggregates. Reports are
saved as `scraped_data/*_report_*.json` (each carrying `owner_id`).

## 5. Frontend rendering (`features/social/report-view.tsx`)

A rich, print-ready report. Chart design follows the repo's chart system (accessible, CVD-checked
categorical palette for the complaint donut; diverging pos/neu/neg for the sentiment-mix area):

- **Complaint-mix donut** (part-to-whole, distinct hues), **rating histogram**, **topic/complaint
  bars**, **trend line**, **sentiment-mix stacked area over time**, **topic momentum**.
- **Per-channel view** with a filter bar (sentiment / source / period) directly under the channel
  tabs, **friction-point** and **strength** cards, and **verbatim/review cards** (`dir="auto"` so
  Arabic renders RTL, sentiment dot + tidy footer, safe date formatting).

## Data model & ownership

Reports are file-based (`scraped_data/`), owner-scoped, shareable (`kind="social_report"`), and
attachable to projects. The dashboard (`features/social/table.tsx`) mirrors the other modules
(open / share / delete / import + "Shared with you" tag).

## Known limitations / notes

- Ad-filtering and the sentiment-mix data apply to **new scrapes** — already-saved reports keep their
  prior classification/aggregates (re-run to apply).
- Scraper reliability varies by platform; post timestamps are not always present (Period filter only
  appears when reviews carry parseable dates).
