"""Decides what a benchmark claim is allowed to say, and whether to go looking for evidence.

Sits above the leaders services: they *fetch* competitor evidence, this decides whether fetching
is warranted and what may be asserted afterwards. `RetrievalDecision` is the interesting type --
a benchmark comparison is expensive (many web searches plus a model pass per candidate), so it is
not run unconditionally.

`MaturityTruth` is the guard against the failure mode this module exists to prevent: a benchmark
that flatters or contradicts the diagnostic. A comparison must stay consistent with the client's
actual scores, so a claim that would imply a maturity the assessment did not find is rejected
rather than published.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import re
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.text_normalization import normalize_text
from app.db.models.capability import Capability
from app.db.models.capability_maturity_rubric import CapabilityMaturityRubric
from app.db.models.maturity_level import MaturityLevel

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BenchmarkEvidenceSignal:
    capability: str
    maturity_band: str
    rationale: str | None = None
    evidence_text: str | None = None


@dataclass(frozen=True)
class BenchmarkQueryContext:
    sector: str
    company_size: str
    priority_axis: str
    pain_points: list[str]
    evidence_signals: list[BenchmarkEvidenceSignal] = field(default_factory=list)


@dataclass(frozen=True)
class CompetitiveCandidate:
    key: str
    company_name: str
    domain: str | None


@dataclass(frozen=True)
class RetrievalDecision:
    query: str
    url: str | None
    title: str | None
    site_name: str | None
    summary: str | None
    status: str
    reason: str
    published_at: str | None = None


@dataclass(frozen=True)
class MaturityTruth:
    level: int
    label: str
    description: str
    rubric_signals: tuple[str, ...]


TELECOM_COMPETITOR_CANDIDATES: tuple[CompetitiveCandidate, ...] = (
    CompetitiveCandidate("vodafone", "Vodafone", "vodafone.com"),
    CompetitiveCandidate("orange", "Orange", "orange.com"),
    CompetitiveCandidate("airtel", "Airtel", "airtel.com"),
    CompetitiveCandidate("du", "du", "du.ae"),
    CompetitiveCandidate("omantel", "Omantel", "omantel.om"),
    CompetitiveCandidate("maroc-telecom", "Maroc Telecom", "iam.ma"),
    CompetitiveCandidate("t-mobile", "T-Mobile", "t-mobile.com"),
    CompetitiveCandidate("telstra", "Telstra", "telstra.com.au"),
    CompetitiveCandidate("verizon", "Verizon", "verizon.com"),
)


class BenchmarkService:
    def __init__(self, db: AsyncSession | None = None) -> None:
        self.db = db
        self.settings = get_settings()
        self._mistral_rate_limited = False

    def get_contextual_benchmarks(self, context: BenchmarkQueryContext) -> list[dict]:
        if not self.settings.langsearch_api_key:
            return []

        queries = self._build_queries(context)
        relevance_terms = self._context_relevance_terms(context)
        all_items_by_url: dict[str, dict] = {}
        seen_urls: set[str] = set()

        for query in queries:
            for item in self._search(query):
                url = str(item.get("url") or "").strip()
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                item["_relevance_score"] = self._score_item_relevance(item=item, terms=relevance_terms)
                item["context_match"] = self._context_match_text(item=item, terms=relevance_terms)
                all_items_by_url[url] = item

        ranked_items = sorted(
            all_items_by_url.values(),
            key=lambda item: (
                -int(item.get("_relevance_score") or 0),
                0 if item.get("published_at") else 1,
                str(item.get("title") or ""),
            ),
        )
        relevant_items = [item for item in ranked_items if int(item.get("_relevance_score") or 0) > 0]
        selected = (relevant_items or ranked_items)[:6]
        for item in selected:
            item["summary"] = self._compact_summary(
                title=str(item.get("title") or ""),
                summary=str(item.get("summary") or ""),
            )
            item.pop("_relevance_score", None)
        return selected

    async def debug_competitive_first_layer(
        self,
        *,
        sector: str,
        company_name: str,
        competitor_name: str | None = None,
    ) -> dict:
        if self._sector_key(sector) != "telecom":
            return {
                "sector": sector,
                "company_name": company_name,
                "supported": False,
                "reason": "DB-driven competitive debug currently supports telecom only.",
                "competitors": [],
            }

        normalized_company_name = normalize_text(company_name).lower()
        candidates = [
            candidate
            for candidate in TELECOM_COMPETITOR_CANDIDATES
            if normalize_text(candidate.company_name).lower() != normalized_company_name
        ]
        if competitor_name:
            requested = normalize_text(competitor_name).lower()
            candidates = [
                candidate
                for candidate in candidates
                if requested in normalize_text(candidate.company_name).lower()
                or requested == normalize_text(candidate.key).lower()
            ]

        competitors_debug: list[dict] = []
        for candidate in candidates:
            retrieval = self._retrieve_candidate_documents_debug(candidate=candidate, sector=sector)
            competitors_debug.append(
                {
                    "key": candidate.key,
                    "company_name": candidate.company_name,
                    "domain": candidate.domain,
                    "queries": retrieval["queries"],
                    "accepted": retrieval["accepted"],
                    "rejected": retrieval["rejected"],
                }
            )

        return {
            "sector": sector,
            "company_name": company_name,
            "supported": True,
            "competitors": competitors_debug,
        }

    async def get_competitive_landscape(
        self,
        *,
        sector: str,
        company_name: str,
        overall_level: int | None,
        company_note: str | None = None,
        company_domain: str | None = None,
    ) -> list[dict]:
        del overall_level, company_note, company_domain

        if self.db is None:
            logger.warning("BenchmarkService requires a DB session for the DB-driven competitive landscape.")
            return []

        if self._sector_key(sector) != "telecom":
            logger.warning("DB-driven competitive landscape prototype currently supports telecom only. sector=%r", sector)
            return []

        maturity_truth = await self._load_maturity_truth()
        if not maturity_truth:
            logger.warning("No maturity truth could be loaded from DB for competitive landscape.")
            return []

        normalized_company_name = normalize_text(company_name).lower()
        candidate_companies = [
            candidate
            for candidate in TELECOM_COMPETITOR_CANDIDATES
            if normalize_text(candidate.company_name).lower() != normalized_company_name
        ]

        ranked_competitors: list[dict] = []
        for candidate in candidate_companies:
            competitor = await self._evaluate_candidate_competitor(
                candidate=candidate,
                sector=sector,
                maturity_truth=maturity_truth,
            )
            if competitor:
                ranked_competitors.append(competitor)

        stage_summaries = self._stage_summaries_from_truth(maturity_truth)
        results: list[dict] = []
        for truth in maturity_truth:
            competitors = [
                item for item in ranked_competitors
                if int(item.get("stage_level") or 0) == truth.level
            ]
            competitors.sort(
                key=lambda item: (
                    -float(item.get("_stage_score") or 0.0),
                    -float(item.get("_confidence_gap") or 0.0),
                    str(item.get("company_name") or ""),
                )
            )
            stage_competitors: list[dict] = []
            for competitor in competitors[:3]:
                clean = dict(competitor)
                clean.pop("_stage_score", None)
                clean.pop("_confidence_gap", None)
                stage_competitors.append(clean)

            results.append(
                {
                    "level": truth.level,
                    "label": truth.label,
                    "summary": stage_summaries.get(truth.level) or truth.description,
                    "competitors": stage_competitors,
                }
            )
        return results

    async def _load_maturity_truth(self) -> list[MaturityTruth]:
        result = await self.db.execute(
            select(
                MaturityLevel.level_number,
                MaturityLevel.label,
                MaturityLevel.description,
                Capability.name,
                CapabilityMaturityRubric.description,
                Capability.evidence_required,
            )
            .join(CapabilityMaturityRubric, CapabilityMaturityRubric.maturity_level_id == MaturityLevel.id)
            .join(Capability, Capability.id == CapabilityMaturityRubric.capability_id)
            .where(MaturityLevel.level_number.in_([1, 2, 3]))
            .order_by(MaturityLevel.level_number.asc(), Capability.sort_order.asc(), Capability.id.asc())
        )
        rows = result.all()

        grouped: dict[int, dict] = {}
        for level_number, label, description, capability_name, rubric_description, evidence_required in rows:
            bucket = grouped.setdefault(
                int(level_number),
                {
                    "label": normalize_text(str(label or "")) or self._stage_label(int(level_number)),
                    "description": normalize_text(str(description or "")) or self._fallback_stage_summary(int(level_number)),
                    "signals": [],
                },
            )
            signal = self._compact_rubric_signal(
                capability_name=str(capability_name or ""),
                rubric_description=str(rubric_description or ""),
                evidence_required=str(evidence_required or ""),
            )
            if signal:
                bucket["signals"].append(signal)

        truth: list[MaturityTruth] = []
        for level in (1, 2, 3):
            bucket = grouped.get(level)
            if not bucket:
                continue
            truth.append(
                MaturityTruth(
                    level=level,
                    label=str(bucket["label"]),
                    description=str(bucket["description"]),
                    rubric_signals=tuple(bucket["signals"][:6]),
                )
            )
        return truth

    def _compact_rubric_signal(self, *, capability_name: str, rubric_description: str, evidence_required: str) -> str | None:
        capability = normalize_text(capability_name).strip()
        rubric = normalize_text(rubric_description).strip()
        evidence = normalize_text(evidence_required).strip()
        if not capability or not rubric:
            return None
        summary = rubric.split(".")[0].strip() or rubric
        summary = re.sub(r"^Level\s+\d+\s*/\s*[A-Za-z ]+:\s*", "", summary, flags=re.IGNORECASE)
        if evidence:
            return f"{capability}: {summary}. Public evidence to look for: {evidence}"
        return f"{capability}: {summary}"

    def _stage_summaries_from_truth(self, maturity_truth: list[MaturityTruth]) -> dict[int, str]:
        return {
            item.level: f"{item.label} maturity: {item.description}"
            for item in maturity_truth
        }

    async def _evaluate_candidate_competitor(
        self,
        *,
        candidate: CompetitiveCandidate,
        sector: str,
        maturity_truth: list[MaturityTruth],
    ) -> dict | None:
        candidate_docs = self._retrieve_candidate_documents(candidate=candidate, sector=sector)
        if not candidate_docs:
            return None

        stage_rankings: list[dict] = []
        for truth in maturity_truth:
            rerank_query = self._build_stage_rerank_query(
                company_name=candidate.company_name,
                sector=sector,
                truth=truth,
            )
            rerank_results = self._semantic_rerank(
                query=rerank_query,
                documents=[doc["document_text"] for doc in candidate_docs],
                top_n=min(6, len(candidate_docs)),
            )
            if not rerank_results:
                continue

            top_results: list[dict] = []
            for item in rerank_results[:3]:
                index = int(item.get("index", -1))
                if index < 0 or index >= len(candidate_docs):
                    continue
                top_results.append(
                    {
                        "doc": candidate_docs[index],
                        "relevance_score": float(item.get("relevance_score") or 0.0),
                    }
                )
            if not top_results:
                continue

            stage_rankings.append(
                {
                    "level": truth.level,
                    "label": truth.label,
                    "description": truth.description,
                    "score": self._aggregate_stage_score(top_results),
                    "evidence": top_results,
                }
            )

        if not stage_rankings:
            return None

        stage_rankings.sort(key=lambda item: (-float(item["score"]), int(item["level"])))
        winner = stage_rankings[0]
        runner_up_score = float(stage_rankings[1]["score"]) if len(stage_rankings) > 1 else 0.0
        evidence_links = self._build_stage_evidence_links(
            company_name=candidate.company_name,
            stage_level=int(winner["level"]),
            evidence=winner["evidence"],
        )
        if not evidence_links:
            return None

        return {
            "key": candidate.key,
            "company_name": candidate.company_name,
            "note": self._build_stage_note(
                company_name=candidate.company_name,
                stage_label=str(winner["label"]),
                stage_description=str(winner["description"]),
            ),
            "stage_level": int(winner["level"]),
            "stage_label": f"Stage {int(winner['level'])} - {winner['label']}",
            "logo_url": None,
            "is_you": False,
            "evidence_links": evidence_links,
            "_stage_score": float(winner["score"]),
            "_confidence_gap": float(winner["score"]) - runner_up_score,
        }

    def _retrieve_candidate_documents(self, *, candidate: CompetitiveCandidate, sector: str) -> list[dict]:
        retrieval = self._retrieve_candidate_documents_debug(candidate=candidate, sector=sector)
        return list(retrieval["accepted"])[:12]

    def _retrieve_candidate_documents_debug(self, *, candidate: CompetitiveCandidate, sector: str) -> dict:
        queries = self._broad_company_queries(company_name=candidate.company_name, sector=sector, domain=candidate.domain)
        docs: list[dict] = []
        rejected: list[dict] = []
        seen_urls: set[str] = set()
        for query in queries:
            for item in self._search(query):
                url = str(item.get("url") or "").strip()
                normalized_title = normalize_text(str(item.get("title") or "")).strip() or None
                site_name = normalize_text(str(item.get("site_name") or "")).strip() or None
                summary = normalize_text(str(item.get("summary") or item.get("snippet") or "")).strip() or None
                published_at = str(item.get("published_at") or "").strip() or None

                if not url:
                    rejected.append(
                        self._retrieval_decision_dict(
                            RetrievalDecision(
                                query=query,
                                url=None,
                                title=normalized_title,
                                site_name=site_name,
                                summary=summary,
                                published_at=published_at,
                                status="rejected",
                                reason="missing_url",
                            )
                        )
                    )
                    continue

                if url in seen_urls:
                    rejected.append(
                        self._retrieval_decision_dict(
                            RetrievalDecision(
                                query=query,
                                url=url,
                                title=normalized_title,
                                site_name=site_name,
                                summary=summary,
                                published_at=published_at,
                                status="rejected",
                                reason="duplicate_url",
                            )
                        )
                    )
                    continue

                rejection_reason = self._competitive_rejection_reason(item=item, domain=candidate.domain)
                if rejection_reason:
                    rejected.append(
                        self._retrieval_decision_dict(
                            RetrievalDecision(
                                query=query,
                                url=url,
                                title=normalized_title,
                                site_name=site_name,
                                summary=summary,
                                published_at=published_at,
                                status="rejected",
                                reason=rejection_reason,
                            )
                        )
                    )
                    continue

                seen_urls.add(url)
                docs.append(
                    {
                        "title": normalized_title,
                        "url": url,
                        "site_name": site_name,
                        "summary": summary,
                        "published_at": published_at,
                        "document_text": self._document_text_for_rerank(item=item),
                        "query": query,
                    }
                )
        return {
            "queries": queries,
            "accepted": docs[:12],
            "rejected": rejected,
        }

    def _broad_company_queries(self, *, company_name: str, sector: str, domain: str | None) -> list[str]:
        normalized_domain = self._normalized_domain(domain)
        domain_hint = f" on {normalized_domain}" if normalized_domain else ""
        return [
            (
                f"Find public pages about how {company_name} operates or improves customer experience in {sector}{domain_hint}, "
                f"including customer support, service improvement, digital care, self-service, or customer journey work."
            ),
            (
                f"Find public evidence showing how {company_name} talks about or delivers customer experience practices in {sector}, "
                f"especially through customer service, service quality, digital experience, or journey improvements{domain_hint}."
            ),
        ]

    def _document_text_for_rerank(self, *, item: dict) -> str:
        parts = [
            f"Title: {normalize_text(str(item.get('title') or '')).strip()}",
            f"Source: {normalize_text(str(item.get('site_name') or '')).strip()}",
            f"Summary: {normalize_text(str(item.get('summary') or item.get('snippet') or '')).strip()}",
            f"URL: {str(item.get('url') or '').strip()}",
        ]
        return "\n".join(part for part in parts if part and not part.endswith(": "))

    def _build_stage_rerank_query(self, *, company_name: str, sector: str, truth: MaturityTruth) -> str:
        signals = "; ".join(truth.rubric_signals[:4])
        return (
            f"Rank these documents by how well they prove that {company_name} belongs to {truth.label} maturity in {sector}. "
            f"The level definition is: {truth.description} "
            f"Prefer documents showing concrete customer-experience operating practices, not generic marketing claims. "
            f"Relevant evidence may include: {signals}"
        )

    def _semantic_rerank(self, *, query: str, documents: list[str], top_n: int) -> list[dict]:
        if not self.settings.langsearch_api_key or not documents:
            return []

        endpoint = self.settings.langsearch_base_url.rstrip("/") + "/rerank"
        payload = {
            "model": "langsearch-reranker-v1",
            "query": query,
            "documents": documents[:50],
            "top_n": min(top_n, len(documents), 50),
            "return_documents": False,
        }
        headers = {
            "Authorization": f"Bearer {self.settings.langsearch_api_key}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=12.0) as client:
                response = client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            logger.warning("Semantic rerank failed for query=%r: %s", query, exc)
            return []
        return list((data or {}).get("results") or [])

    def _aggregate_stage_score(self, top_results: list[dict]) -> float:
        if not top_results:
            return 0.0
        weighted = 0.0
        total_weight = 0.0
        for index, item in enumerate(top_results):
            weight = 1.0 / (index + 1)
            weighted += float(item.get("relevance_score") or 0.0) * weight
            total_weight += weight
        return weighted / total_weight if total_weight else 0.0

    def _build_stage_evidence_links(self, *, company_name: str, stage_level: int, evidence: list[dict]) -> list[dict[str, str]]:
        links: list[dict[str, str]] = []
        used_urls: set[str] = set()
        for item in evidence:
            doc = item["doc"]
            url = str(doc.get("url") or "").strip()
            if not url or url in used_urls:
                continue
            used_urls.add(url)
            label = self._evidence_sentence_from_document(
                company_name=company_name,
                stage_level=stage_level,
                title=str(doc.get("title") or ""),
                summary=str(doc.get("summary") or ""),
            )
            if not label:
                continue
            links.append(
                {
                    "label": label,
                    "url": url,
                    "source_title": normalize_text(str(doc.get("title") or "")).strip() or None,
                }
            )
        return links[:3]

    def _evidence_sentence_from_document(self, *, company_name: str, stage_level: int, title: str, summary: str) -> str | None:
        clean_summary = normalize_text(summary).strip()
        clean_title = normalize_text(title).strip()
        if clean_summary:
            sentence = clean_summary.split(".")[0].strip()
            if sentence and len(sentence) > 24:
                return sentence
        if clean_title:
            return f"{company_name} has public evidence aligned with stage {stage_level}: {clean_title}"
        return None

    def _build_stage_note(self, *, company_name: str, stage_label: str, stage_description: str) -> str:
        return f"{company_name} most strongly matches {stage_label} maturity because the public evidence aligns with this maturity pattern: {stage_description}"

    def _url_matches_domain(self, url: str, domain: str | None) -> bool:
        if not domain:
            return False
        host = self._domain_host(url)
        normalized_domain = self._normalized_domain(domain)
        return bool(host and (host == normalized_domain or host.endswith(f".{normalized_domain}")))

    def _domain_host(self, url: str) -> str:
        parsed = urlparse(str(url or "").strip())
        host = normalize_text(parsed.netloc or "").lower()
        return host.removeprefix("www.")

    def _normalized_domain(self, value: str | None) -> str:
        parsed = urlparse(str(value or "").strip())
        host = parsed.netloc or str(value or "")
        return normalize_text(host).lower().removeprefix("www.").strip("/")

    def _competitive_rejection_reason(self, *, item: dict, domain: str | None) -> str | None:
        url = str(item.get("url") or "").strip()
        title = normalize_text(str(item.get("title") or "")).lower()
        summary = normalize_text(str(item.get("summary") or item.get("snippet") or "")).lower()
        host = self._domain_host(url)

        blocked_hosts = {
            "apps.apple.com",
            "play.google.com",
            "justuseapp.com",
            "gethuman.com",
            "productreview.com.au",
            "complaintsboard.com",
            "dearcustomercare.com",
            "consumeraffairs.com",
            "sitejabber.com",
            "trustpilot.com",
        }
        if host in blocked_hosts:
            return "blocked_host"

        blocked_title_terms = (
            "privacy policy",
            "ratings & reviews",
            "customer service phone number",
            "is safe or legit",
            "frequently asked questions",
            "faq",
            "complaints",
        )
        if any(term in title for term in blocked_title_terms):
            return "blocked_title_pattern"

        if "review" in title and not self._url_matches_domain(url, domain):
            return "generic_review_page"
        if "support" in title and "customer experience" not in title and not self._url_matches_domain(url, domain):
            return "generic_support_page"
        if "privacy" in summary:
            return "privacy_content"
        return None

    def _is_low_quality_competitive_result(self, *, item: dict, domain: str | None) -> bool:
        return self._competitive_rejection_reason(item=item, domain=domain) is not None

    def _retrieval_decision_dict(self, decision: RetrievalDecision) -> dict:
        return {
            "query": decision.query,
            "url": decision.url,
            "title": decision.title,
            "site_name": decision.site_name,
            "summary": decision.summary,
            "published_at": decision.published_at,
            "status": decision.status,
            "reason": decision.reason,
        }

    def _stage_label(self, level: int) -> str:
        return {1: "Basic", 2: "Established", 3: "Advanced"}.get(level, "Stage")

    def _fallback_stage_summary(self, level: int) -> str:
        return {
            1: "Organizations here are still operating customer experience with limited systemization.",
            2: "Organizations here show meaningful progress but still need stronger consistency across the journey.",
            3: "Organizations here treat customer experience as a coordinated growth engine.",
        }[level]

    def _sector_key(self, sector: str) -> str:
        sample = normalize_text(sector).lower()
        if any(term in sample for term in ("travel", "tour", "hospitality", "destination", "leisure")):
            return "travel"
        if any(term in sample for term in ("retail", "commerce", "ecommerce", "consumer", "fashion", "beauty")):
            return "retail"
        if any(term in sample for term in ("finance", "bank", "insurance", "fintech", "wealth")):
            return "finance"
        if any(term in sample for term in ("telecom", "telecommunications", "telco", "mobile", "operator", "carrier", "connectivity")):
            return "telecom"
        if any(term in sample for term in ("software", "saas", "technology", "tech", "platform")):
            return "saas"
        if any(term in sample for term in ("health", "clinic", "medical", "care", "wellness")):
            return "health"
        return "default"

    def _build_queries(self, context: BenchmarkQueryContext) -> list[str]:
        sector = self._safe_query_part(context.sector)
        size = self._safe_query_part(context.company_size)
        priority_axis = self._safe_query_part(context.priority_axis)
        pain_hint = self._safe_query_part(" ".join(context.pain_points[:2]))
        evidence_hint = self._safe_query_part(" ".join(self._evidence_search_terms(context)[:5]))
        capability_hint = self._safe_query_part(
            " ".join(signal.capability for signal in context.evidence_signals[:3] if signal.capability)
        )

        queries = [
            (
                f"Find public case studies, benchmark articles, or credible examples about customer experience in the {sector} sector "
                f"for {size} companies, especially around {capability_hint or 'core CX practices'} and {evidence_hint or 'observable CX evidence'}. english"
            ),
            (
                f"Find customer experience best practices in {sector} that relate to {pain_hint or 'common customer pain points'} "
                f"and show how organizations improved them in practice. english"
            ),
            (
                f"Find public examples of CX operating models in {sector}, especially around {priority_axis or 'priority customer experience themes'} "
                f"and {capability_hint or 'practical service design capabilities'}. english"
            ),
            f"Find recent customer experience innovation examples in the {sector} sector from 2025 or 2026. english",
        ]
        return [re.sub(r"\s+", " ", query).strip() for query in queries if query.strip()]

    def _search(self, query: str) -> list[dict]:
        endpoint = self.settings.langsearch_base_url.rstrip("/") + "/web-search"
        headers = {
            "Authorization": f"Bearer {self.settings.langsearch_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "query": query,
            "freshness": "oneYear",
            "summary": True,
            "count": 3,
        }
        try:
            with httpx.Client(timeout=8.0) as client:
                response = client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            logger.warning("Benchmark search failed for query=%r: %s", query, exc)
            return []

        envelope = (data or {}).get("data") or {}
        values = ((envelope.get("webPages") or {}).get("value")) or []
        items: list[dict] = []
        for value in values:
            title = normalize_text(str(value.get("name") or ""))
            url = str(value.get("url") or "").strip()
            snippet = normalize_text(str(value.get("snippet") or ""))
            summary = normalize_text(str(value.get("summary") or ""))
            published_at = value.get("datePublished")
            site_name = normalize_text(str(value.get("siteName") or ""))
            if not title or not url:
                continue
            items.append(
                {
                    "title": title,
                    "url": url,
                    "site_name": site_name or None,
                    "published_at": str(published_at) if published_at else None,
                    "summary": summary or snippet or None,
                    "method_signal": self._infer_method_signal(text=f"{title} {snippet} {summary}"),
                    "snippet": snippet or None,
                }
            )
        return items

    def _infer_method_signal(self, text: str) -> str | None:
        sample = text.lower()
        if "personalization" in sample:
            return "Personalization at scale"
        if "journey" in sample:
            return "Journey-led operating model"
        if "voice of customer" in sample or "voc" in sample:
            return "Closed-loop VoC"
        if "agent" in sample or "copilot" in sample or "ai" in sample:
            return "AI-assisted customer operations"
        if "omnichannel" in sample:
            return "Omnichannel consistency"
        return None

    def _compact_summary(self, title: str, summary: str) -> str | None:
        raw = self._clean_summary_text(summary)
        if not raw:
            return None
        if len(raw) <= 320:
            return raw
        llm_text = self._summarize_with_llm(title=title, text=raw)
        if llm_text:
            return self._clean_summary_text(llm_text)
        return raw[:317].rstrip() + "..."

    def _summarize_with_llm(self, title: str, text: str) -> str | None:
        if not self.settings.mistral_api_key or self._mistral_rate_limited:
            return None

        prompt = (
            "Summarize this benchmark source for a business report.\n"
            "Output only 2 short sentences (max 55 words total).\n"
            "Focus on concrete CX/innovation practice and potential business impact.\n"
            f"Title: {title}\n"
            f"Content: {text[:3000]}"
        )
        try:
            with httpx.Client(timeout=20.0) as client:
                response = client.post(
                    self.settings.mistral_base_url.rstrip("/") + "/chat/completions",
                    headers={"Authorization": f"Bearer {self.settings.mistral_api_key}"},
                    json={
                        "model": self.settings.mistral_model,
                        "temperature": 0.2,
                        "messages": [
                            {"role": "system", "content": "You write concise executive summaries."},
                            {"role": "user", "content": prompt},
                        ],
                    },
                )
                response.raise_for_status()
                data = response.json()
                content = (((data or {}).get("choices") or [{}])[0].get("message") or {}).get("content")
                compact = self._clean_summary_text(str(content or ""))
                if not compact:
                    return None
                if len(compact) > 380:
                    return compact[:377].rstrip() + "..."
                return compact
        except httpx.HTTPStatusError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                self._mistral_rate_limited = True
                logger.warning("Mistral rate limit reached during benchmark summary compaction; using raw summaries.")
                return None
            logger.warning("Benchmark summary compaction failed for title=%r: %s", title, exc)
            return None
        except Exception as exc:
            logger.warning("Benchmark summary compaction failed for title=%r: %s", title, exc)
            return None

    def _clean_summary_text(self, text: str) -> str:
        cleaned = normalize_text(text)
        replacements = {
            "ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢": "'",
            "ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ": '"',
            "ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â": '"',
            "ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“": "-",
            "ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â": "-",
            "ÃƒÆ’Ã‚Â©": "e",
        }
        for bad, good in replacements.items():
            cleaned = cleaned.replace(bad, good)
        cleaned = cleaned.replace("**", "")
        cleaned = re.sub(r"^\s*Executive Summary:\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _evidence_search_terms(self, context: BenchmarkQueryContext) -> list[str]:
        raw_parts: list[str] = []
        for signal in context.evidence_signals[:6]:
            raw_parts.extend(
                [
                    signal.capability,
                    signal.maturity_band,
                    signal.rationale or "",
                    signal.evidence_text or "",
                ]
            )
        raw_parts.extend(context.pain_points)
        return self._extract_terms(" ".join(raw_parts), max_terms=12)

    def _context_relevance_terms(self, context: BenchmarkQueryContext) -> list[str]:
        terms = [
            *self._extract_terms(context.sector, max_terms=4),
            *self._extract_terms(context.priority_axis, max_terms=4),
            *self._extract_terms(" ".join(context.pain_points), max_terms=8),
            *self._evidence_search_terms(context),
        ]
        return self._dedupe_terms(terms)[:20]

    def _extract_terms(self, text: str, max_terms: int) -> list[str]:
        normalized = normalize_text(text).lower()
        normalized = re.sub(r"[^a-z0-9\s-]", " ", normalized)
        words = [word for word in re.split(r"\s+", normalized) if self._is_relevant_word(word)]
        phrases = [
            " ".join(words[index : index + 2])
            for index in range(max(0, len(words) - 1))
            if len(words[index]) >= 3 and len(words[index + 1]) >= 3
        ]
        return self._dedupe_terms([*phrases, *words])[:max_terms]

    def _is_relevant_word(self, word: str) -> bool:
        if len(word) < 3:
            return False
        stopwords = {
            "and",
            "are",
            "but",
            "can",
            "the",
            "this",
            "that",
            "their",
            "there",
            "with",
            "from",
            "into",
            "they",
            "user",
            "answer",
            "evidence",
            "maturity",
            "level",
            "basic",
            "advanced",
            "established",
            "current",
            "customer",
            "customers",
            "experience",
            "assessment",
        }
        return word not in stopwords

    def _dedupe_terms(self, terms: list[str]) -> list[str]:
        unique: list[str] = []
        seen: set[str] = set()
        for term in terms:
            clean = normalize_text(term).lower()
            if not clean or clean in seen:
                continue
            seen.add(clean)
            unique.append(clean)
        return unique

    def _score_item_relevance(self, item: dict, terms: list[str]) -> int:
        if not terms:
            return 0
        title = normalize_text(str(item.get("title") or "")).lower()
        summary = normalize_text(str(item.get("summary") or item.get("snippet") or "")).lower()
        score = 0
        for term in terms:
            if term in title:
                score += 4 if " " in term else 2
            if term in summary:
                score += 2 if " " in term else 1
        return score

    def _context_match_text(self, item: dict, terms: list[str]) -> str | None:
        if not terms:
            return None
        text = normalize_text(
            f"{item.get('title') or ''} {item.get('summary') or ''} {item.get('snippet') or ''}"
        ).lower()
        matched = [term for term in terms if term in text][:3]
        if not matched:
            return None
        return f"Relevant to: {', '.join(matched)}"

    def _safe_query_part(self, value: str) -> str:
        cleaned = normalize_text(value)
        cleaned = re.sub(r"[^a-zA-Z0-9\s-]", " ", cleaned)
        return re.sub(r"\s+", " ", cleaned).strip()
