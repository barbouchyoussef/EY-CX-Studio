"""Social-media scraping service powered by Apify and Bright Data."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone

import httpx
import os

from app.schemas.manual_analysis import ManualAnalysisWorkbook
from app.schemas.scraping import (
    PlatformResult,
    ScrapedReview,
    ScrapingResponse,
)
from app.services.scraping.classification_service import classify_reviews
from app.services.scraping.social_report_service import generate_detailed_social_report

logger = logging.getLogger(__name__)

_APIFY_BASE = "https://api.apify.com/v2"
_RUN_TIMEOUT = 480  # 8 minutes timeout for Apify actor runs to prevent premature timeout
_HTTP_TIMEOUT = 500.0  # httpx timeout (must exceed _RUN_TIMEOUT)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _save_raw_data(platform: str, brand: str, items: list[dict]):
    """Safely archive raw scraped data to a local JSON file."""
    try:
        os.makedirs("scraped_data", exist_ok=True)
        safe_brand = re.sub(r"[^a-zA-Z0-9_-]", "_", brand.strip().lower())
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"scraped_data/{safe_brand}_{platform.lower().replace(' ', '_')}_{timestamp}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
        logger.info("Saved raw scraped data for %s on %s to %s", brand, platform, filename)
    except Exception as e:
        logger.warning("Failed to save raw scraped data for %s on %s: %s", brand, platform, e)


# Statuses worth retrying: the provider is briefly unhealthy, the work itself is fine.
_TRANSIENT_STATUSES = {408, 425, 429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 4
_POLL_INTERVAL = 4


def _redact(text: str) -> str:
    """Strip credentials from anything that may be logged, stored or shown to a user.

    httpx puts the full URL in its error text, so a token passed as a query parameter ends
    up inside exception messages -- which are persisted to the report JSON, the job row and
    the browser. Auth now travels in a header, and this is the belt-and-braces net for any
    other path (a provider echoing the URL back, a hardcoded key in a message, ...).
    """
    if not text:
        return text
    redacted = re.sub(r"([?&](?:token|key|api_key|apiKey)=)[^&\s\"']+", r"\1***", text)
    redacted = re.sub(r"\bapify_api_[A-Za-z0-9]+", "apify_api_***", redacted)
    redacted = re.sub(r"(Bearer\s+)[A-Za-z0-9._\-]+", r"\1***", redacted)
    return redacted


def _apify_headers(token: str) -> dict:
    """Bearer auth keeps the token out of URLs, and therefore out of error text and logs."""
    return {"Authorization": f"Bearer {token}"}


async def _request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    headers: dict | None = None,
    json_body: dict | None = None,
    what: str = "request",
) -> httpx.Response:
    """Issue a request, retrying transient provider failures with exponential backoff.

    Used for the one-shot calls (starting a run, fetching the dataset) where giving up
    means losing work already paid for. A non-transient status fails immediately -- retrying
    a 401 or a 404 only wastes time.
    """
    last_error: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            response = await client.request(method, url, headers=headers, json=json_body)
            if response.status_code in _TRANSIENT_STATUSES:
                raise httpx.HTTPStatusError(
                    f"transient {response.status_code}", request=response.request, response=response
                )
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in _TRANSIENT_STATUSES:
                raise
            last_error = exc
        except httpx.TransportError as exc:  # timeouts, connection resets, DNS failures
            last_error = exc

        if attempt < _MAX_ATTEMPTS:
            delay = 2**attempt  # 2s, 4s, 8s
            logger.warning(
                "%s failed (attempt %d/%d): %s -- retrying in %ds",
                what, attempt, _MAX_ATTEMPTS, _redact(str(last_error))[:200], delay,
            )
            await asyncio.sleep(delay)

    raise RuntimeError(f"{what} failed after {_MAX_ATTEMPTS} attempts: {_redact(str(last_error))[:200]}")


async def _run_actor(
    client: httpx.AsyncClient,
    actor_id: str,
    token: str,
    run_input: dict,
    *,
    memory_mb: int = 2048,
    timeout: int = _RUN_TIMEOUT,
) -> list[dict]:
    """Run an Apify actor asynchronously and poll for results to prevent gateway timeouts."""
    headers = _apify_headers(token)

    start_resp = await _request_with_retry(
        client,
        "POST",
        f"{_APIFY_BASE}/acts/{actor_id}/runs?memory={memory_mb}",
        headers=headers,
        json_body=run_input,
        what=f"Apify start run for {actor_id}",
    )
    run_data = start_resp.json().get("data", {})
    run_id = run_data.get("id")
    dataset_id = run_data.get("defaultDatasetId")

    if not run_id or not dataset_id:
        raise ValueError(f"Failed to start actor run for {actor_id}")

    status_url = f"{_APIFY_BASE}/actor-runs/{run_id}"
    start_time = datetime.now(timezone.utc)
    consecutive_poll_errors = 0

    while (datetime.now(timezone.utc) - start_time).total_seconds() < timeout:
        try:
            status_resp = await client.get(status_url, headers=headers)
            status_resp.raise_for_status()
        except (httpx.HTTPStatusError, httpx.TransportError) as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if status_code is not None and status_code not in _TRANSIENT_STATUSES:
                raise
            # The actor keeps running on Apify regardless of our ability to ask about it, so
            # a blip must not discard a scrape that is still in progress and already billed.
            consecutive_poll_errors += 1
            logger.warning(
                "Apify status poll failed for run %s (%d in a row): %s -- still polling",
                run_id, consecutive_poll_errors, _redact(str(exc))[:200],
            )
            await asyncio.sleep(min(_POLL_INTERVAL * consecutive_poll_errors, 30))
            continue

        consecutive_poll_errors = 0
        try:
            run_status = status_resp.json().get("data", {}).get("status")
        except (ValueError, KeyError):
            consecutive_poll_errors += 1
            logger.warning("Apify poll returned non-JSON for run %s — retrying", run_id)
            await asyncio.sleep(min(_POLL_INTERVAL * consecutive_poll_errors, 30))
            continue

        if run_status == "SUCCEEDED":
            # The run is done and paid for; this fetch is the last place to lose it.
            items_resp = await _request_with_retry(
                client,
                "GET",
                f"{_APIFY_BASE}/datasets/{dataset_id}/items",
                headers=headers,
                what=f"Apify dataset fetch for run {run_id}",
            )
            return items_resp.json()
        if run_status in ("FAILED", "TIMED-OUT", "ABORTED"):
            raise RuntimeError(f"Actor run {run_id} finished with status: {run_status}")

        await asyncio.sleep(_POLL_INTERVAL)

    raise TimeoutError(f"Actor run {run_id} timed out after {timeout} seconds")


def _parse_brightdata_response(content_bytes: bytes) -> list[dict]:
    """Parse Bright Data response which can be standard JSON or JSON Lines (NDJSON)."""
    text = content_bytes.decode("utf-8").strip()
    if not text:
        return []
    
    # Try parsing as JSON Lines (NDJSON)
    lines = text.splitlines()
    if len(lines) > 1 or (lines and lines[0].startswith("{") and lines[0].endswith("}")):
        try:
            return [json.loads(line) for line in lines if line.strip()]
        except Exception:
            pass
            
    # Fallback to standard JSON
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return [data]
    except Exception:
        pass
        
    raise ValueError(f"Failed to parse Bright Data response: {text[:200]}")


async def _run_brightdata_dataset(
    client: httpx.AsyncClient,
    dataset_id: str,
    bearer_token: str,
    inputs: list[dict],
) -> list[dict]:
    """Trigger a Bright Data dataset scrape and return the results."""
    url = f"https://api.brightdata.com/datasets/v3/scrape?dataset_id={dataset_id}&notify=false&include_errors=true"
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "input": inputs,
        "limit_per_input": None,
    }
    
    logger.info("Triggering Bright Data dataset scrape for ID: %s", dataset_id)
    resp = await _request_with_retry(
        client, "POST", url, headers=headers, json_body=payload,
        what=f"Bright Data trigger for dataset {dataset_id}",
    )

    parsed = _parse_brightdata_response(resp.content)

    # If the response is a metadata dict with snapshot_id, we poll
    if len(parsed) == 1 and "snapshot_id" in parsed[0]:
        snapshot_id = parsed[0]["snapshot_id"]
        logger.info("Bright Data async snapshot created: %s. Polling...", snapshot_id)

        progress_url = f"https://api.brightdata.com/datasets/v3/progress/{snapshot_id}"
        snapshot_url = f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}"
        auth = {"Authorization": f"Bearer {bearer_token}"}

        start_time = datetime.now(timezone.utc)
        consecutive_poll_errors = 0
        while (datetime.now(timezone.utc) - start_time).total_seconds() < 180:
            try:
                p_resp = await client.get(progress_url, headers=auth)
                p_resp.raise_for_status()
            except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                status_code = getattr(getattr(exc, "response", None), "status_code", None)
                if status_code is not None and status_code not in _TRANSIENT_STATUSES:
                    raise
                # Same reasoning as the Apify poll: the snapshot keeps building regardless.
                consecutive_poll_errors += 1
                logger.warning(
                    "Bright Data progress poll failed for %s (%d in a row): %s -- still polling",
                    snapshot_id, consecutive_poll_errors, _redact(str(exc))[:200],
                )
                await asyncio.sleep(min(5 * consecutive_poll_errors, 30))
                continue

            consecutive_poll_errors = 0
            try:
                status = p_resp.json().get("status")
            except (ValueError, KeyError):
                consecutive_poll_errors += 1
                logger.warning("Bright Data poll returned non-JSON for %s — retrying", snapshot_id)
                await asyncio.sleep(min(5 * consecutive_poll_errors, 30))
                continue
            logger.info("Bright Data snapshot %s status: %s", snapshot_id, status)

            if status == "ready":
                d_resp = await _request_with_retry(
                    client, "GET", snapshot_url, headers=auth,
                    what=f"Bright Data snapshot fetch {snapshot_id}",
                )
                return _parse_brightdata_response(d_resp.content)
            if status in ("failed", "cancelled"):
                raise RuntimeError(f"Bright Data dataset run failed: {status}")

            await asyncio.sleep(5)

        raise TimeoutError(f"Bright Data snapshot {snapshot_id} timed out")

    return parsed


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except Exception:
        if isinstance(val, str):
            m = re.search(r"[-+]?\d*\.\d+|\d+", val)
            if m:
                try:
                    return float(m.group(0))
                except Exception:
                    pass
        return None


# ISO codes for the countries this is realistically used in, plus the French and English
# spellings that turn up in Apify addresses. Anything not listed still works via the
# free-text address match below, so the map only has to cover the common cases.
_COUNTRY_ALIASES = {
    "tn": {"tunisie", "tunisia", "tn"},
    "fr": {"france", "fr"},
    "ma": {"maroc", "morocco", "ma"},
    "dz": {"algerie", "algeria", "dz"},
    "be": {"belgique", "belgium", "be"},
    "ch": {"suisse", "switzerland", "ch"},
    "ca": {"canada", "ca"},
    "us": {"etats-unis", "united states", "usa", "us"},
    "gb": {"royaume-uni", "united kingdom", "uk", "gb"},
    "de": {"allemagne", "germany", "de"},
    "es": {"espagne", "spain", "es"},
    "it": {"italie", "italy", "it"},
    "eg": {"egypte", "egypt", "eg"},
    "sa": {"arabie saoudite", "saudi arabia", "sa"},
    "ae": {"emirats arabes unis", "united arab emirates", "uae", "ae"},
}


def _fold_text(value: str) -> str:
    """Lowercase and strip accents so 'Tunisie' and 'TUNISIE' compare equal."""
    import unicodedata

    stripped = unicodedata.normalize("NFKD", (value or "").casefold())
    return "".join(ch for ch in stripped if not unicodedata.combining(ch))


def _location_matches(item: dict, location: str) -> bool:
    """Return True if a Google Maps place sits in the requested country or city.

    A brand-name search is global: 'Mytek' returned IT firms in Phoenix and wholesalers in
    Mexico alongside nothing from Tunisia. Name matching cannot separate them -- every one
    of those places legitimately contains 'mytek' -- so geography is the only discriminator.

    Matching is per-token: consultants type things like "Mytek Tunisie" or "Tunis, Tunisia",
    and requiring the whole string to match would reject every genuine place.
    """
    wanted = _fold_text(location).strip()
    if not wanted:
        return True

    tokens = [t for t in re.split(r"[^a-z0-9]+", wanted) if len(t) > 1]
    if not tokens:
        return True

    country_code = _fold_text(str(item.get("countryCode") or ""))
    aliases = _COUNTRY_ALIASES.get(country_code, {country_code}) if country_code else set()

    haystack = " ".join(
        _fold_text(str(item.get(f) or ""))
        for f in ("address", "city", "state", "neighborhood", "street")
    )

    for token in tokens:
        # Country code or one of its spellings ("tn", "tunisie", "tunisia").
        if token in aliases:
            return True
        # A city or region typed instead of the country ("tunis" -> TN, "ariana").
        if any(len(a) > 2 and (a.startswith(token) or token.startswith(a)) for a in aliases):
            return True
        # Anything appearing in the human-readable address fields.
        if len(token) > 2 and token in haystack:
            return True
    return False


def _is_relevant_comment(text: str) -> bool:
    """Return True if the text seems to be a relevant customer comment/feedback rather than spam or tags."""
    if not text:
        return False
    text_clean = text.strip()
    # Check length: if less than 12 characters, probably just "up", "mrc", "top", or an emoji
    if len(text_clean) < 12:
        return False
    # Check if it is just a user tag (e.g. "@Name Name")
    if text_clean.startswith("@"):
        return False
    # If the text has only name-like patterns (e.g. 2-3 capitalized words) and nothing else, ignore
    words = text_clean.split()
    if len(words) <= 3 and all(w[0].isupper() for w in words if w and w[0].isalpha()):
        return False
    return True


def _format_date_val(val) -> str | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        try:
            # Check if millisecond timestamp
            if val > 1e11:
                val = val / 1000.0
            dt = datetime.fromtimestamp(val, tz=timezone.utc)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return str(val)
    if isinstance(val, str):
        val_strip = val.strip()
        if val_strip.isdigit():
            try:
                numeric_val = float(val_strip)
                if numeric_val > 1e11:
                    numeric_val = numeric_val / 1000.0
                dt = datetime.fromtimestamp(numeric_val, tz=timezone.utc)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass
        return val_strip
    return str(val)


# ---------------------------------------------------------------------------
# Google Maps Reviews
# ---------------------------------------------------------------------------

async def _scrape_google_maps(
    client: httpx.AsyncClient, brand: str, token: str, location: str | None = None,
) -> PlatformResult:
    """Scrape Google Maps reviews for the given brand, restricted to `location`."""
    try:
        actor_input: dict = {
            "startUrls": [],
            "searchStringsArray": [brand],
            "maxReviews": 40,
            "language": "fr",
            # Reviewer identities are never used analytically, and the saved report is
            # kept on disk, so we do not collect them at all (GDPR / INPDP data minimisation).
            "personalData": False,
        }
        if location and location.strip():
            # Narrows the search server-side; the post-filter below is the real guarantee.
            actor_input["locationQuery"] = location.strip()

        items = await _run_actor(
            client,
            "compass~google-maps-reviews-scraper",
            token,
            actor_input,
            memory_mb=2048,
        )
        _save_raw_data("Google Maps", brand, items)

        # Drop places outside the requested location before anything is counted. Without
        # this a generic brand name silently blends unrelated businesses from other
        # countries into the sentiment, and the report reads perfectly while being wrong.
        matched_places: set[str] = set()
        excluded_places: set[str] = set()
        if location and location.strip():
            kept: list[dict] = []
            for item in items:
                title = (item.get("title") or "?").strip()
                if _location_matches(item, location):
                    kept.append(item)
                    matched_places.add(title)
                else:
                    excluded_places.add(title)
            if excluded_places:
                logger.info(
                    "Google Maps: kept %d/%d reviews for '%s' in '%s'; excluded places: %s",
                    len(kept), len(items), brand, location, sorted(excluded_places),
                )
            items = kept
        else:
            for item in items:
                matched_places.add((item.get("title") or "?").strip())
            logger.warning(
                "Google Maps scraped '%s' with no location filter -- results may include "
                "same-named businesses elsewhere. Matched places: %s",
                brand, sorted(matched_places),
            )

        if not items:
            return PlatformResult(
                platform="Google Maps",
                status="empty",
                excluded_places=sorted(excluded_places),
            )

        reviews: list[ScrapedReview] = []
        for item in items:
            text = (item.get("text") or item.get("textTranslated") or "").strip()
            rating = _safe_float(item.get("stars") or item.get("reviewRating"))
            # A star with no comment is still a customer verdict. Dropping these threw away
            # the majority of the rating data (468 raw items collapsed to 196), which made
            # the star distribution -- the most defensible figure in the report -- rest on a
            # fraction of what was available. Only items with neither text nor rating are useless.
            if not text and rating is None:
                continue
            reviews.append(
                ScrapedReview(
                    platform="Google Maps",
                    author=item.get("name") or item.get("reviewerName"),
                    text=text,
                    rating=rating,
                    date=_format_date_val(item.get("publishedAtDate") or item.get("reviewDate")),
                    url=item.get("reviewUrl") or item.get("url"),
                )
            )

        if not reviews:
            return PlatformResult(
                platform="Google Maps",
                status="empty",
                excluded_places=sorted(excluded_places),
            )

        return PlatformResult(
            platform="Google Maps",
            status="success",
            review_count=len(reviews),
            reviews=reviews,
            matched_places=sorted(matched_places),
            excluded_places=sorted(excluded_places),
        )
    except (RuntimeError, TimeoutError) as exc:
        logger.error("Google Maps scraping failed for '%s': %s", brand, exc)
        return PlatformResult(
            platform="Google Maps",
            status="error",
            error_message=_redact(str(exc))[:300],
        )
    except Exception as exc:
        logger.exception("Google Maps scraping failed for '%s' with unexpected error", brand)
        return PlatformResult(
            platform="Google Maps",
            status="error",
            error_message=_redact(str(exc))[:300],
        )


# ---------------------------------------------------------------------------
# Trustpilot
# ---------------------------------------------------------------------------

_TRUSTPILOT_ACTOR = "automation-lab~trustpilot"
_TRUSTPILOT_PERIODS = {"", "last30days", "last3months", "last6months", "last12months"}


def _normalize_trustpilot_domain(value: str) -> str:
    """Accept a bare domain, a URL, or a full Trustpilot review URL and return the domain."""
    cleaned = value.strip()
    if not cleaned:
        return ""
    # Full Trustpilot URL -> take the segment after /review/
    match = re.search(r"trustpilot\.[a-z.]+/review/([^/?#]+)", cleaned, re.IGNORECASE)
    if match:
        return match.group(1)
    cleaned = re.sub(r"^https?://", "", cleaned, flags=re.IGNORECASE)
    return cleaned.split("/")[0].strip()


async def _scrape_trustpilot(
    client: httpx.AsyncClient,
    brand: str,
    token: str,
    domain: str | None,
    period: str | None = None,
) -> PlatformResult:
    """Scrape Trustpilot reviews for a company domain.

    Skipped unless a domain is supplied: guessing it from the brand name produces the
    wrong company far too often to be trustworthy in a client deliverable.
    """
    normalized = _normalize_trustpilot_domain(domain or "")
    if not normalized:
        return PlatformResult(platform="Trustpilot", status="empty")

    window = period if period in _TRUSTPILOT_PERIODS else ""

    try:
        items = await _run_actor(
            client,
            _TRUSTPILOT_ACTOR,
            token,
            {
                "companyUrls": [normalized],
                "maxReviewsPerCompany": 60,
                "sort": "recency",          # newest first, so the sample tracks the reporting period
                "date": window,
                "includeCompanyInfo": True,
            },
            memory_mb=1024,
        )
        _save_raw_data("Trustpilot", brand, items)

        reviews: list[ScrapedReview] = []
        replied = 0
        summary_stat: str | None = None

        for item in items:
            # Trustpilot titles are usually a truncated head of the body, so prefer the body.
            body = (item.get("text") or "").strip()
            title = (item.get("title") or "").strip()
            text = body or title
            rating = _safe_float(item.get("rating"))
            if not text and rating is None:
                continue
            if item.get("replyMessage"):
                replied += 1
            reviews.append(
                ScrapedReview(
                    platform="Trustpilot",
                    author=item.get("authorName"),
                    text=text,
                    rating=rating,
                    date=_format_date_val(item.get("publishedDate") or item.get("experienceDate")),
                    url=item.get("reviewUrl"),
                )
            )
            if summary_stat is None and item.get("companyTrustScore") is not None:
                total = item.get("companyTotalReviews")
                score = item.get("companyTrustScore")
                summary_stat = f"TrustScore {score}/5" + (f" · {total:,} reviews total" if total else "")

        if not reviews:
            return PlatformResult(platform="Trustpilot", status="empty")

        return PlatformResult(
            platform="Trustpilot",
            status="success",
            review_count=len(reviews),
            reviews=reviews,
            summary_stat=summary_stat,
            reply_rate_pct=round(replied / len(reviews) * 100, 1) if reviews else None,
        )
    except (RuntimeError, TimeoutError) as exc:
        logger.error("Trustpilot scraping failed for '%s': %s", brand, exc)
        return PlatformResult(platform="Trustpilot", status="error", error_message=_redact(str(exc))[:300])
    except Exception as exc:
        logger.exception("Trustpilot scraping failed for '%s' with unexpected error", brand)
        return PlatformResult(platform="Trustpilot", status="error", error_message=_redact(str(exc))[:300])


# ---------------------------------------------------------------------------
# Facebook
# ---------------------------------------------------------------------------

def _resolve_facebook_url(brand: str) -> str:
    brand_clean = brand.strip()
    if brand_clean.startswith("http://") or brand_clean.startswith("https://"):
        return brand_clean
    if "facebook.com/" in brand_clean.lower():
        if not brand_clean.lower().startswith("http"):
            return f"https://{brand_clean}"
        return brand_clean
    # Remove characters that are not alphanumeric or hyphens/dots
    clean_handle = re.sub(r"[^a-zA-Z0-9.-]", "", brand_clean)
    return f"https://www.facebook.com/{clean_handle}/"


def _parse_facebook_urls(value: str | None, brand: str) -> list[str]:
    """Parse a single or comma/newline-separated string of Facebook URLs or handles."""
    if not value or not value.strip():
        return [_resolve_facebook_url(brand)]

    raw_parts = re.split(r"[\n,;]+", value.strip())
    resolved: list[str] = []
    seen: set[str] = set()
    for part in raw_parts:
        part_clean = part.strip()
        if not part_clean:
            continue
        url = _resolve_facebook_url(part_clean)
        if url and "facebook.com/" in url.lower() and url not in seen:
            seen.add(url)
            resolved.append(url)

    return resolved if resolved else [_resolve_facebook_url(brand)]


async def _scrape_facebook_single_page(
    client: httpx.AsyncClient,
    brand: str,
    bd_token: str,
    posts_dataset_id: str,
    comments_dataset_id: str,
    page_url: str,
) -> tuple[list[ScrapedReview], str | None]:
    """Scrape a single Facebook page URL robustly.

    Swallows page-level non-fatal errors (e.g. invalid URL, 404, no posts) so
    other pages in a multi-page request continue without interrupting the pipeline.
    """
    logger.info("Resolving Facebook posts via Bright Data for page: %s", page_url)
    posts_inputs = [{"url": page_url, "num_of_posts": 10}]
    try:
        posts = await _run_brightdata_dataset(client, posts_dataset_id, bd_token, posts_inputs)
    except httpx.HTTPStatusError as http_err:
        body_text = http_err.response.text
        if "Customer is not active" in body_text:
            raise http_err  # Re-raise account status errors
        logger.warning("Facebook single page scrape HTTP error for %s: %s", page_url, http_err)
        return [], page_url
    except Exception as exc:
        logger.warning("Facebook single page scrape failed for %s: %s", page_url, exc)
        return [], page_url

    post_urls = [p.get("url") for p in posts if p.get("url") and ("/posts/" in p.get("url") or "pfbid" in p.get("url"))]
    if not post_urls:
        logger.warning("No public post URLs resolved for Facebook page: %s", page_url)
        return [], page_url

    logger.info("Scraping Facebook comments from %d posts on page: %s", len(post_urls), page_url)
    comments_inputs = [{"url": purl, "limit_records": 15} for purl in post_urls]
    try:
        comments = await _run_brightdata_dataset(client, comments_dataset_id, bd_token, comments_inputs)
    except Exception as exc:
        logger.warning("Facebook comments fetch failed for %s: %s", page_url, exc)
        return [], page_url

    _save_raw_data("Facebook", brand, comments)

    reviews: list[ScrapedReview] = []
    for item in comments:
        if "error" in item:
            err_msg = item.get("error") or ""
            if "no comments" in err_msg.lower():
                logger.info("Bright Data post has no comments: %s", item.get("input", {}).get("url"))
            else:
                logger.warning("Bright Data comment item error: %s", err_msg)
            continue

        text = (item.get("comment_text") or "").strip()
        if not _is_relevant_comment(text):
            continue

        author = item.get("user_name") or "Anonymous"
        reviews.append(
            ScrapedReview(
                platform="Facebook",
                author=author,
                text=text,
                date=_format_date_val(item.get("date_created") or item.get("timestamp")),
                url=item.get("comment_link") or item.get("post_url"),
                source="page",  # comments on the brand's official Facebook page
            )
        )
    return reviews, page_url


_NON_FEEDBACK_KEYWORDS = [
    "عرض عمل", "مطلوب", "recrutement", "offre d'emploi", "cherche un travail",
    "سيرة ذاتية", "شغور", "مطلوب منشط", "animateur de vente", "recrute",
    "rabais", "concours", "ربح", "تشارك", "شارك و إربح"
]


def _is_customer_feedback(text: str) -> bool:
    """Filter out job offers, recruitment ads, and promotional contest spam."""
    if not text or len(text.strip()) < 15:
        return False
    text_lower = text.lower()
    for kw in _NON_FEEDBACK_KEYWORDS:
        if kw in text_lower:
            return False
    return True


async def _scrape_facebook_keywords(
    client: httpx.AsyncClient, brand: str, token: str, keywords: str | None = None
) -> list[ScrapedReview]:
    """Scrape public Facebook post & comment mentions by keyword via Apify."""
    query_str = keywords.strip() if keywords and keywords.strip() else brand
    logger.info("Scraping Facebook keyword mentions via Apify for query: '%s'", query_str)
    
    try:
        raw_items = await _run_actor(
            client,
            actor_id="scrapeforge~facebook-search-posts",
            token=token,
            run_input={"query": query_str, "max_results": 15},
            memory_mb=2048,
            timeout=120,
        )
        reviews: list[ScrapedReview] = []
        for idx, item in enumerate(raw_items, 1):
            text = item.get("message") or item.get("postText") or item.get("content") or ""
            if not _is_customer_feedback(text):
                continue
            post_id = item.get("post_id") or str(idx)
            url = item.get("url") or f"https://www.facebook.com/search/posts/?q={query_str}"
            timestamp_val = str(item.get("timestamp") or "")

            reviews.append(
                ScrapedReview(
                    platform="Facebook",
                    author="Anonymous",  # Presented anonymously as requested
                    text=text,
                    rating=None,
                    date=timestamp_val,
                    url=url,
                    source="keyword",  # public mention found via keyword search
                )
            )
        logger.info("Retained %d valid Facebook keyword mention review(s) for '%s'", len(reviews), query_str)
        return reviews
    except Exception as exc:
        logger.warning("Apify Facebook keyword search failed for '%s': %s", query_str, exc)
        return []


async def _scrape_facebook(
    client: httpx.AsyncClient,
    brand: str,
    token: str,
    facebook_url: str | None = None,
    keywords: str | None = None,
) -> PlatformResult:
    """Scrape Facebook comments across pages (Bright Data) and keyword mentions (Apify) concurrently."""
    try:
        urls = _parse_facebook_urls(facebook_url, brand)
        all_reviews: list[ScrapedReview] = []
        matched_places: list[str] = []
        fatal_error: str | None = None

        tasks = []
        # 1. Page Scraper task via Bright Data (if URLs exist and a token is configured)
        bd_token = os.getenv("BRIGHTDATA_API_TOKEN", "")
        if urls and bd_token:
            posts_dataset_id = os.getenv("BRIGHTDATA_FB_POSTS_DATASET_ID", "gd_lkaxegm826bjpoo9m5")
            comments_dataset_id = os.getenv("BRIGHTDATA_FB_COMMENTS_DATASET_ID", "gd_lkay758p1eanlolqw8")
            for page_url in urls:
                tasks.append(
                    _scrape_facebook_single_page(client, brand, bd_token, posts_dataset_id, comments_dataset_id, page_url)
                )

        # 2. Keyword Mentions task via Apify (if keywords provided OR if no page URLs provided)
        should_run_keywords = bool(keywords and keywords.strip()) or not urls
        if should_run_keywords:
            tasks.append(_scrape_facebook_keywords(client, brand, token, keywords))

        if not tasks:
            return PlatformResult(platform="Facebook", status="empty")

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for res in results:
            if isinstance(res, Exception):
                err_text = getattr(getattr(res, "response", None), "text", "")
                if isinstance(res, httpx.HTTPStatusError) and "Customer is not active" in err_text:
                    fatal_error = "Bright Data API error: Customer is not active. Please fund/activate your account."
                continue
            if isinstance(res, tuple):
                reviews, page_url = res
                if reviews:
                    all_reviews.extend(reviews)
                if page_url:
                    matched_places.append(page_url)
            elif isinstance(res, list):
                all_reviews.extend(res)
                matched_places.append(f"Keyword Mentions ('{keywords.strip() if keywords else brand}')")

        if fatal_error and not all_reviews:
            return PlatformResult(platform="Facebook", status="error", error_message=fatal_error)

        if not all_reviews:
            return PlatformResult(
                platform="Facebook",
                status="empty",
                matched_places=matched_places,
            )

        return PlatformResult(
            platform="Facebook",
            status="success",
            review_count=len(all_reviews),
            reviews=all_reviews,
            matched_places=matched_places,
        )
    except (RuntimeError, TimeoutError) as exc:
        logger.error("Facebook comments & keyword scraping failed for '%s': %s", brand, exc)
        return PlatformResult(
            platform="Facebook",
            status="error",
            error_message=_redact(str(exc))[:300],
        )
    except Exception as exc:
        logger.exception("Facebook comments & keyword scraping failed for '%s' with unexpected error", brand)
        return PlatformResult(
            platform="Facebook",
            status="error",
            error_message=_redact(str(exc))[:300],
        )


def _is_meaningful_instagram_comment(text: str) -> bool:
    """Filter out emoji-only, tag-only (@user), single-word, spam, and non-feedback Instagram comments."""
    if not text:
        return False
    text_clean = text.strip()
    text_no_mentions = re.sub(r'@[A-Za-z0-9._-]+', '', text_clean).strip()
    if len(text_no_mentions) < 10:
        return False
    letters_only = re.sub(r'[^\w\s\u0600-\u06FF]', '', text_no_mentions)
    if len(letters_only.strip()) < 6:
        return False
    text_lower = text_clean.lower()
    for kw in _NON_FEEDBACK_KEYWORDS:
        if kw in text_lower:
            return False
    return True


async def _scrape_instagram(
    client: httpx.AsyncClient, brand: str, token: str, instagram_url: str | None = None
) -> PlatformResult:
    """Scrape Instagram profile posts & comments using an automated 2-step pipeline via Apify."""
    if not instagram_url or not instagram_url.strip():
        return PlatformResult(platform="Instagram", status="empty")

    clean_input = instagram_url.strip()
    logger.info("Scraping Instagram for brand '%s' with input: %s", brand, clean_input)

    try:
        # Step 1: Discover recent post URLs from Instagram Profile or handle
        username = clean_input.split("?")[0].rstrip("/").split("/")[-1].replace("@", "")
        clean_profile_url = f"https://www.instagram.com/{username}/"

        posts_data = await _run_actor(
            client,
            actor_id="apify~instagram-scraper",
            token=token,
            run_input={
                "directUrls": [clean_profile_url],
                "resultsType": "posts",
                "resultsLimit": 5,
            },
            memory_mb=2048,
            timeout=90,
        )

        post_urls = []
        for item in posts_data:
            short_code = item.get("shortCode")
            if short_code:
                post_urls.append(f"https://www.instagram.com/p/{short_code}/")
            elif item.get("url") and ("/p/" in item["url"] or "/reel/" in item["url"]):
                post_urls.append(item["url"])

        if not post_urls:
            return PlatformResult(
                platform="Instagram",
                status="empty",
                matched_places=[clean_profile_url],
            )

        # Step 2: Fetch comments under discovered posts/reels
        raw_comments = await _run_actor(
            client,
            actor_id="apify~instagram-comment-scraper",
            token=token,
            run_input={"directUrls": post_urls, "resultsLimit": 25},
            memory_mb=2048,
            timeout=90,
        )

        reviews: list[ScrapedReview] = []
        for idx, c in enumerate(raw_comments, 1):
            text = c.get("text") or c.get("commentText") or ""
            post_url = c.get("postUrl") or post_urls[0]
            timestamp_val = str(c.get("timestamp") or c.get("created_at") or "")

            if _is_meaningful_instagram_comment(text):
                reviews.append(
                    ScrapedReview(
                        platform="Instagram",
                        author="Anonymous",  # Presented anonymously as requested
                        rating=None,
                        text=text,
                        date=timestamp_val,
                        url=post_url,
                    )
                )

        if not reviews:
            return PlatformResult(
                platform="Instagram",
                status="empty",
                matched_places=[clean_profile_url],
            )

        return PlatformResult(
            platform="Instagram",
            status="success",
            review_count=len(reviews),
            reviews=reviews,
            matched_places=[clean_profile_url],
        )

    except Exception as exc:
        logger.exception("Instagram scraping failed for '%s'", brand)
        return PlatformResult(
            platform="Instagram",
            status="error",
            error_message=_redact(str(exc))[:300],
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def run_full_scrape(
    brand_name: str,
    apify_token: str,
    facebook_url: str | None = None,
    manual_analysis: ManualAnalysisWorkbook | None = None,
    trustpilot_domain: str | None = None,
    trustpilot_period: str | None = None,
    google_location: str | None = None,
    keywords: str | None = None,
    instagram_url: str | None = None,
) -> ScrapingResponse:
    """Run all scrapers concurrently and return a unified result."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(_HTTP_TIMEOUT)) as client:
        # We run gather with return_exceptions=True to ensure that one failure doesn't crash the entire pipeline
        results = await asyncio.gather(
            _scrape_google_maps(client, brand_name, apify_token, google_location),
            _scrape_facebook(client, brand_name, apify_token, facebook_url, keywords),
            _scrape_trustpilot(client, brand_name, apify_token, trustpilot_domain, trustpilot_period),
            _scrape_instagram(client, brand_name, apify_token, instagram_url),
            return_exceptions=True
        )

    # Process results, checking for exceptions
    platforms = []
    platform_names = ["Google Maps", "Facebook", "Trustpilot", "Instagram"]
    for res, platform_name in zip(results, platform_names):
        if isinstance(res, Exception):
            logger.error("%s scraping raised exception: %s", platform_name, res, exc_info=True)
            platforms.append(
                PlatformResult(
                    platform=platform_name,
                    status="error",
                    error_message=f"System exception: {_redact(str(res))[:150]}",
                )
            )
        else:
            platforms.append(res)

    total = sum(p.review_count for p in platforms)

    # Classify successfully scraped reviews in a batch
    all_reviews = []
    for p in platforms:
        if p.status == "success" and p.reviews:
            all_reviews.extend(p.reviews)

    analysis = None
    if all_reviews:
        try:
            _, analysis = await classify_reviews(all_reviews, brand_name)
        except Exception:
            logger.exception("Failed to classify reviews for '%s'", brand_name)

    # One unified report covering everything available: always generated when there is any
    # data at all -- scraped reviews and/or the consultant's manual analysis.
    detailed_report = None
    if all_reviews or manual_analysis is not None:
        try:
            detailed_report = await generate_detailed_social_report(brand_name, platforms, manual_analysis)
        except Exception:
            logger.exception("Failed to generate detailed social report for '%s'", brand_name)

    return ScrapingResponse(
        brand_name=brand_name,
        scraped_at=datetime.now(timezone.utc).isoformat(),
        platforms=platforms,
        total_reviews=total,
        analysis=analysis,
        detailed_report=detailed_report,
        manual_analysis=manual_analysis,
    )

