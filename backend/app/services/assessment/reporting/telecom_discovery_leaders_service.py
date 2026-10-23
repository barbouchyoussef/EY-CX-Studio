"""Finds benchmark candidates by search when no curated shortlist covers the sector.

The counterpart to `telecom_semantic_leaders_service`, which starts from the vetted list in
`sector_leader_candidates`. This one starts from nothing and discovers candidates, so it is the
fallback for sectors that have not been curated.

The trade is worth knowing before reading the code: discovery covers any sector but is only as
good as what search returns on the day, so results are less stable and need heavier filtering.
Curated candidates are preferred wherever they exist -- reproducibility matters more than reach
in a report a consultant has to defend.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

import httpx

from app.core.config import Settings, get_settings
from app.core.text_normalization import normalize_text
from app.services.llm.utils import extract_json

if TYPE_CHECKING:
    from app.services.llm.core.facade_service import LLMService

logger = logging.getLogger(__name__)


class TelecomDiscoveryLeadersService:
    def __init__(self, settings: Settings | None = None, llm_service: "LLMService | None" = None) -> None:
        self.settings = settings or get_settings()
        self.llm = llm_service

    async def build_leaders_snapshot(
        self,
        *,
        sector: str,
        respondent_company_name: str,
        pain_points: list[dict[str, str | None]],
        include_debug: bool = False,
    ) -> dict[str, Any]:
        if "telecom" not in normalize_text(sector).lower():
            return {
                "supported": False,
                "reason": "This discovery-first semantic leaders prototype currently supports telecom only.",
                "sector": sector,
                "respondent_company_name": respondent_company_name,
                "leaders": [],
            }
        if not self.settings.langsearch_api_key:
            return {
                "supported": False,
                "reason": "LANGSEARCH_API_KEY is not configured.",
                "sector": sector,
                "respondent_company_name": respondent_company_name,
                "leaders": [],
            }

        benchmark_brief = self._build_benchmark_brief(pain_points)
        discovery_queries = self._build_discovery_queries(sector=sector, benchmark_brief=benchmark_brief)
        discovery_documents = await self._web_search_candidates(discovery_queries, max_documents=12, per_query_count=6)
        discovery_ranked = await self._semantic_rerank(
            query=self._build_discovery_rerank_query(sector=sector, benchmark_brief=benchmark_brief),
            documents=[self._document_text(item) for item in discovery_documents],
            top_n=min(10, len(discovery_documents)),
        )
        ranked_discovery_documents = self._reorder_documents(discovery_documents, discovery_ranked) or discovery_documents

        discovered_companies = await self._extract_discovered_companies(
            respondent_company_name=respondent_company_name,
            documents=ranked_discovery_documents,
        )
        candidate_pool = self._score_discovered_companies(
            companies=discovered_companies,
            respondent_company_name=respondent_company_name,
        )

        leaders: list[dict[str, Any]] = []
        candidate_debug: list[dict[str, Any]] = []
        for candidate in candidate_pool[:8]:
            leader = await self._evaluate_company_candidate(
                candidate_name=str(candidate["company_name"]),
                sector=sector,
                pain_points=pain_points,
                support_count=int(candidate["support_count"]),
                discovery_score=float(candidate["discovery_score"]),
                include_debug=include_debug,
            )
            if leader:
                leaders.append(leader)
                if include_debug and isinstance(leader.get("_debug"), dict):
                    candidate_debug.append(leader["_debug"])
            elif include_debug:
                candidate_debug.append(
                    {
                        "company_name": candidate["company_name"],
                        "support_count": candidate["support_count"],
                        "discovery_score": candidate["discovery_score"],
                        "reason": "candidate_returned_none",
                    }
                )

        leaders.sort(
            key=lambda item: (
                -float(item.get("_semantic_score") or 0.0),
                -int(len(item.get("evidence_links") or [])),
                str(item.get("company_name") or ""),
            )
        )

        trimmed: list[dict[str, Any]] = []
        for item in leaders[:3]:
            clean = dict(item)
            clean.pop("_semantic_score", None)
            clean.pop("_debug", None)
            trimmed.append(clean)

        payload: dict[str, Any] = {
            "supported": True,
            "sector": sector,
            "respondent_company_name": respondent_company_name,
            "pain_points": pain_points,
            "benchmark_brief": benchmark_brief,
            "discovery_queries": discovery_queries,
            "leaders": trimmed,
        }
        if include_debug:
            payload["discovery_documents"] = ranked_discovery_documents
            payload["discovered_companies"] = candidate_pool
            payload["candidate_debug"] = candidate_debug
        return payload

    def _build_benchmark_brief(self, pain_points: list[dict[str, str | None]]) -> str:
        parts: list[str] = []
        for item in pain_points[:3]:
            capability = normalize_text(str(item.get("capability") or "")).strip()
            detail = self._sanitized_pain_point_detail(item)
            level = item.get("maturity_number")
            if capability and detail:
                level_prefix = f"Current level {level}: " if level else ""
                parts.append(f"{capability}: {level_prefix}{detail}")
            elif capability:
                parts.append(capability)
        return " | ".join(parts) if parts else "customer feedback, service quality, and decision-making gaps"

    def _build_discovery_queries(self, *, sector: str, benchmark_brief: str) -> list[str]:
        return [
            (
                f"Find telecom companies with public case studies, reports, or articles showing strong customer experience "
                f"practices relevant to these gaps: {benchmark_brief}. Prefer concrete operating practices, feedback loops, "
                f"service assurance, customer support, journey improvements, analytics, and decision-making examples. english"
            ),
            (
                f"Which telecom companies publicly demonstrate strong customer-experience practices for these topics: "
                f"{benchmark_brief}? Find recent case studies, operational examples, and detailed benchmark articles. english"
            ),
        ]

    def _build_discovery_rerank_query(self, *, sector: str, benchmark_brief: str) -> str:
        return (
            f"Rank these documents by how well they help discover strong telecom benchmark leaders for this brief: {benchmark_brief}. "
            f"Prefer documents that name a telecom company and describe concrete customer-experience practices, feedback loops, "
            f"service assurance, decision-making, journey improvement, or measurable CX change. "
            f"Penalize broad sector commentary with no company focus."
        )

    async def _extract_discovered_companies(
        self,
        *,
        respondent_company_name: str,
        documents: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not documents or self.llm is None:
            return []
        document_block = []
        for index, doc in enumerate(documents[:10], 1):
            document_block.append(
                f"{index}. Title: {normalize_text(str(doc.get('title') or '')).strip()}\n"
                f"   Summary: {normalize_text(str(doc.get('summary') or '')).strip()}\n"
                f"   URL: {str(doc.get('url') or '').strip()}"
            )
        try:
            content = await self.llm.gateway.chat_messages(
                [
                    {
                        "role": "system",
                        "content": (
                            "Extract telecom companies that appear to be relevant benchmark leaders from search results. "
                            "Return STRICT JSON only with this shape: "
                            "{\"companies\":[{\"company_name\":\"...\",\"result_indexes\":[1,2]}]}. "
                            "Only include company names explicitly mentioned or clearly the focal company of a result. "
                            "Exclude the respondent company and generic entities like analysts, vendors, or publications."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Respondent company: {respondent_company_name}\n\n"
                            f"Search results:\n{chr(10).join(document_block)}"
                        ),
                    },
                ]
            )
        except Exception as exc:
            logger.warning("Telecom discovery extraction failed: %s", exc)
            return []
        blob = extract_json(str(content or "")) or {}
        companies = blob.get("companies")
        return companies if isinstance(companies, list) else []

    def _score_discovered_companies(
        self,
        *,
        companies: list[dict[str, Any]],
        respondent_company_name: str,
    ) -> list[dict[str, Any]]:
        normalized_respondent = self._normalize_company_key(respondent_company_name)
        scored: dict[str, dict[str, Any]] = {}
        for item in companies:
            company_name = normalize_text(str(item.get("company_name") or "")).strip()
            if not company_name:
                continue
            key = self._normalize_company_key(company_name)
            if not key or key == normalized_respondent:
                continue
            result_indexes = item.get("result_indexes") if isinstance(item.get("result_indexes"), list) else []
            support_indexes = sorted(
                {
                    int(index)
                    for index in result_indexes
                    if isinstance(index, int) or (isinstance(index, str) and str(index).isdigit())
                }
            )
            entry = scored.setdefault(
                key,
                {
                    "company_name": company_name,
                    "support_count": 0,
                    "discovery_score": 0.0,
                    "result_indexes": set(),
                },
            )
            if len(company_name) > len(str(entry["company_name"])):
                entry["company_name"] = company_name
            for index in support_indexes:
                if index in entry["result_indexes"]:
                    continue
                entry["result_indexes"].add(index)
                entry["support_count"] += 1
                entry["discovery_score"] += max(0.0, 1.0 - ((index - 1) * 0.08))

        ranked = sorted(
            scored.values(),
            key=lambda item: (
                -int(item["support_count"]),
                -float(item["discovery_score"]),
                str(item["company_name"]),
            ),
        )
        cleaned: list[dict[str, Any]] = []
        for item in ranked:
            cleaned.append(
                {
                    "company_name": item["company_name"],
                    "support_count": item["support_count"],
                    "discovery_score": round(float(item["discovery_score"]), 4),
                    "result_indexes": sorted(item["result_indexes"]),
                }
            )
        return cleaned

    async def _evaluate_company_candidate(
        self,
        *,
        candidate_name: str,
        sector: str,
        pain_points: list[dict[str, str | None]],
        support_count: int,
        discovery_score: float,
        include_debug: bool,
    ) -> dict[str, Any] | None:
        search_queries = self._build_company_queries(
            company_name=candidate_name,
            sector=sector,
            pain_points=pain_points,
        )
        retrieved_documents = await self._web_search_candidates(search_queries, max_documents=12, per_query_count=6)
        if not retrieved_documents:
            return None

        candidate_quality_query = self._build_candidate_quality_query(
            company_name=candidate_name,
            sector=sector,
            pain_points=pain_points,
        )
        candidate_quality_ranked = await self._semantic_rerank(
            query=candidate_quality_query,
            documents=[self._document_text(item) for item in retrieved_documents],
            top_n=min(8, len(retrieved_documents)),
        )
        if candidate_quality_ranked:
            quality_documents = self._reorder_documents(retrieved_documents, candidate_quality_ranked)
            if quality_documents:
                retrieved_documents = quality_documents

        rerank_query = self._build_pain_point_rerank_query(
            company_name=candidate_name,
            sector=sector,
            pain_points=pain_points,
        )
        reranked = await self._semantic_rerank(
            query=rerank_query,
            documents=[self._document_text(item) for item in retrieved_documents],
            top_n=min(8, len(retrieved_documents)),
        )
        if not reranked:
            return None

        evidence_links: list[dict[str, str | None]] = []
        unique_urls: set[str] = set()
        unique_domains: set[str] = set()
        semantic_dedup_cache: list[dict[str, Any]] = []
        semantic_dedup_skips = 0
        aggregate_score = 0.0
        rank_count = 0

        for result in reranked:
            index = int(result.get("index", -1))
            if index < 0 or index >= len(retrieved_documents):
                continue
            document = retrieved_documents[index]
            url = str(document.get("url") or "").strip()
            if not url or url in unique_urls:
                continue
            if await self._is_semantic_duplicate(semantic_dedup_cache, document):
                semantic_dedup_skips += 1
                continue
            unique_urls.add(url)
            domain = self._url_domain(url)
            if domain:
                unique_domains.add(domain)
            semantic_dedup_cache.append(document)
            rank_count += 1
            relevance_score = float(result.get("relevance_score") or 0.0)
            aggregate_score += relevance_score / rank_count
            evidence_links.append(
                {
                    "label": await self._rewrite_evidence_label(
                        company_name=candidate_name,
                        title=self._clean_evidence_text(str(document.get("title") or "")),
                        summary=self._best_source_summary(document),
                    ),
                    "url": url,
                    "source_title": document.get("title"),
                }
            )
            if len(evidence_links) >= 3:
                break

        if not evidence_links:
            return None

        aggregate_score += min(len(evidence_links), 3) * 0.1
        aggregate_score += min(len(unique_domains), 3) * 0.05
        aggregate_score += min(support_count, 3) * 0.08
        aggregate_score += min(discovery_score, 3.0) * 0.05

        logo_domain = await self._infer_company_domain(company_name=candidate_name, documents=retrieved_documents)
        payload: dict[str, Any] = {
            "key": self._normalize_company_key(candidate_name),
            "company_name": candidate_name,
            "logo_url": f"https://logo.clearbit.com/{logo_domain}" if logo_domain else None,
            "search_query": search_queries[0],
            "search_queries": search_queries,
            "rerank_query": rerank_query,
            "evidence_links": evidence_links,
            "_semantic_score": aggregate_score,
        }
        if include_debug:
            payload["_debug"] = {
                "company_name": candidate_name,
                "support_count": support_count,
                "discovery_score": discovery_score,
                "retrieved_count": len(retrieved_documents),
                "reranked_count": len(reranked),
                "semantic_dedup_skips": semantic_dedup_skips,
                "selected_count": len(evidence_links),
                "logo_domain": logo_domain,
                "reason": "selected",
            }
        return payload

    def _build_company_queries(
        self,
        *,
        company_name: str,
        sector: str,
        pain_points: list[dict[str, str | None]],
    ) -> list[str]:
        pain_summary = self._pain_point_summary(pain_points)
        return [
            (
                f"Find {company_name}'s documented operating practices, case studies, and detailed reports on "
                f"{pain_summary} in {sector}. Look for evidence of customer feedback handling, service assurance, "
                f"decision-making, analytics, self-service, or customer-support improvements. Prefer sources from 2023 or newer. english"
            ),
            (
                f"Find recent public case studies or detailed articles showing how {company_name} improves customer experience "
                f"in {sector}, especially through feedback loops, service assurance, customer support, self-service, analytics, "
                f"or decision-making practices related to {pain_summary}. Prefer concrete examples over company background. english"
            ),
            (
                f"Find official or third-party evidence of how {company_name} handles customer feedback, pain-point resolution, "
                f"service assurance, or customer-informed decisions in {sector}. Prefer concrete operating examples, case studies, "
                f"or transformation evidence instead of company profile pages. english"
            ),
        ]

    def _build_candidate_quality_query(
        self,
        *,
        company_name: str,
        sector: str,
        pain_points: list[dict[str, str | None]],
    ) -> str:
        pain_summary = self._pain_point_summary(pain_points)
        return (
            f"Rank these documents by how likely they are to be strong benchmark evidence about {company_name} in {sector} "
            f"for these topics: {pain_summary}. Prefer concrete customer-experience practices, case studies, service changes, "
            f"feedback handling, decision-making processes, operational improvements, or measurable outcomes. "
            f"Penalize company background, broad annual-report introductions, generic corporate descriptions, investor boilerplate, "
            f"and documents focused mainly on network scale or market position without customer-experience practices."
        )

    def _build_pain_point_rerank_query(
        self,
        *,
        company_name: str,
        sector: str,
        pain_points: list[dict[str, str | None]],
    ) -> str:
        pain_details = self._pain_point_details_formatted(pain_points)
        return (
            f"Rank these documents by how well they show concrete evidence of what {company_name} is doing "
            f"in {sector} to address these specific customer experience gaps:\n\n"
            f"{pain_details}\n\n"
            f"Prefer evidence of:\n"
            f"- Operating models and team structures\n"
            f"- Formal processes, systems, or tools\n"
            f"- Measurable outcomes or capability improvements\n"
            f"- Governance or accountability structures\n"
            f"- Structured feedback, action loops, or customer-informed decisions\n\n"
            f"Avoid generic claims like enhancing experience or transforming service without concrete details.\n"
            f"Reward documents that clearly address one or more of these pain points with observable practices."
        )

    async def _web_search_candidates(self, queries: list[str], *, max_documents: int, per_query_count: int) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for query in queries:
            for item in await self._web_search(query, count=per_query_count):
                url = str(item.get("url") or "").strip()
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                merged.append(item)
                if len(merged) >= max_documents:
                    return merged
        return merged

    async def _web_search(self, query: str, *, count: int) -> list[dict[str, Any]]:
        endpoint = self.settings.langsearch_base_url.rstrip("/") + "/web-search"
        headers = {
            "Authorization": f"Bearer {self.settings.langsearch_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "query": query,
            "freshness": "oneYear",
            "summary": True,
            "count": count,
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            logger.warning("Telecom discovery web search failed for query=%r: %s", query, exc)
            return []

        values = ((((data or {}).get("data") or {}).get("webPages") or {}).get("value")) or []
        items: list[dict[str, Any]] = []
        for value in values:
            title = normalize_text(str(value.get("name") or "")).strip()
            url = str(value.get("url") or "").strip()
            summary = normalize_text(str(value.get("summary") or value.get("snippet") or "")).strip()
            site_name = normalize_text(str(value.get("siteName") or "")).strip() or None
            if not title or not url:
                continue
            items.append(
                {
                    "title": title,
                    "url": url,
                    "summary": summary or None,
                    "site_name": site_name,
                }
            )
        return items

    async def _semantic_rerank(self, *, query: str, documents: list[str], top_n: int) -> list[dict[str, Any]]:
        if not documents:
            return []
        endpoint = self.settings.langsearch_base_url.rstrip("/") + "/rerank"
        headers = {
            "Authorization": f"Bearer {self.settings.langsearch_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "langsearch-reranker-v1",
            "query": query,
            "documents": documents,
            "top_n": min(top_n, len(documents)),
            "return_documents": False,
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            logger.warning("Telecom discovery rerank failed for query=%r: %s", query, exc)
            return []
        return list((data or {}).get("results") or [])

    def _reorder_documents(self, documents: list[dict[str, Any]], ranked: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not ranked:
            return []
        reordered: list[dict[str, Any]] = []
        seen_indexes: set[int] = set()
        for result in ranked:
            index = int(result.get("index", -1))
            if index < 0 or index >= len(documents) or index in seen_indexes:
                continue
            seen_indexes.add(index)
            reordered.append(documents[index])
        return reordered

    def _document_text(self, item: dict[str, Any]) -> str:
        parts = [
            f"Title: {normalize_text(str(item.get('title') or '')).strip()}",
            f"Source: {normalize_text(str(item.get('site_name') or '')).strip()}",
            f"Summary: {normalize_text(str(item.get('summary') or '')).strip()}",
            f"URL: {str(item.get('url') or '').strip()}",
        ]
        return "\n".join(part for part in parts if part and not part.endswith(": "))

    def _pain_point_summary(self, pain_points: list[dict[str, str | None]]) -> str:
        labels = [
            normalize_text(str(item.get("capability") or "")).strip()
            for item in pain_points[:3]
            if normalize_text(str(item.get("capability") or "")).strip()
        ]
        return ", ".join(labels) if labels else "customer feedback, service quality, and decision-making"

    def _pain_point_details_formatted(self, pain_points: list[dict[str, str | None]]) -> str:
        details: list[str] = []
        for idx, item in enumerate(pain_points[:3], 1):
            capability = normalize_text(str(item.get("capability") or "")).strip()
            detail = self._sanitized_pain_point_detail(item)
            if not capability:
                continue
            if detail:
                details.append(f"{idx}. {capability}:\n   {detail}")
            else:
                details.append(f"{idx}. {capability}")
        return "\n".join(details) if details else "customer feedback, service quality, and digital experience"

    def _sanitized_pain_point_detail(self, item: dict[str, str | None]) -> str:
        source = normalize_text(str(item.get("rubric_description") or item.get("rationale") or "")).strip()
        if not source:
            return ""
        source = re.sub(r"^Level\s+\d+\s*/\s*[^:]+:\s*", "", source, flags=re.IGNORECASE).strip()
        kept: list[str] = []
        for sentence in self._summary_sentences(source):
            lowered = sentence.lower()
            if lowered.startswith("the user may"):
                continue
            if "user wording" in lowered or "did not provide assessable business evidence" in lowered:
                continue
            kept.append(sentence)
        return self._clean_evidence_text(" ".join(kept).strip())

    def _summary_sentences(self, text: str) -> list[str]:
        normalized = normalize_text(text).replace("\n", " ").strip()
        if not normalized:
            return []
        return [part.strip(" -") for part in re.split(r"(?<=[\.\!\?])\s+", normalized) if part.strip(" -")]

    def _clean_evidence_text(self, text: str) -> str:
        value = normalize_text(text).replace("\n", " ").strip(" -")
        value = re.sub(r"^\s*transcript\s*", "", value, flags=re.IGNORECASE).strip(" -")
        value = re.sub(r"^\[\s*music\s*\]\s*", "", value, flags=re.IGNORECASE).strip(" -")
        value = re.sub(r"^\s*by\s+[a-z0-9 ,.'/-]+\s*", "", value, flags=re.IGNORECASE).strip(" -")
        value = re.sub(r"\s+", " ", value).strip()
        return value[:280].strip(" -,:;")

    def _best_source_summary(self, document: dict[str, Any]) -> str:
        summary = normalize_text(str(document.get("summary") or "")).strip()
        title = normalize_text(str(document.get("title") or "")).strip()
        for sentence in self._summary_sentences(summary):
            cleaned = self._clean_evidence_text(sentence)
            if cleaned:
                return cleaned
        return self._clean_evidence_text(title)

    async def _rewrite_evidence_label(self, *, company_name: str, title: str, summary: str) -> str:
        source_text = summary or title or company_name
        if self.llm is None:
            return source_text
        try:
            content = await self.llm.gateway.chat_messages(
                [
                    {
                        "role": "system",
                        "content": (
                            "Rewrite telecom benchmark evidence into one concise, evidence-faithful sentence. "
                            "Use only facts explicitly stated in the title or source summary. "
                            "Do not infer numbers, outcomes, tools, governance, or improvements that are not clearly present. "
                            "If the source is vague, keep the sentence vague rather than making it stronger. "
                            "Avoid transcript markers, filler, hype, and generic marketing language. "
                            "Return only one sentence under 28 words."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Company: {company_name}\n"
                            f"Title: {title}\n"
                            f"Source summary: {summary or title}\n\n"
                            "Write a clean report-tick sentence that stays faithful to the provided evidence only."
                        ),
                    },
                ]
            )
        except Exception as exc:
            logger.warning("Discovery evidence label rewrite failed for %r: %s", company_name, exc)
            return source_text
        cleaned = self._clean_evidence_text(str(content or ""))
        return cleaned or source_text

    async def _is_semantic_duplicate(self, existing_docs: list[dict[str, Any]], candidate: dict[str, Any]) -> bool:
        if not existing_docs or self.llm is None:
            return False
        candidate_title = self._clean_evidence_text(str(candidate.get("title") or ""))
        candidate_summary = self._clean_evidence_text(str(candidate.get("summary") or ""))
        if not candidate_title and not candidate_summary:
            return False
        for existing in existing_docs:
            existing_title = self._clean_evidence_text(str(existing.get("title") or ""))
            existing_summary = self._clean_evidence_text(str(existing.get("summary") or ""))
            try:
                content = await self.llm.gateway.chat_messages(
                    [
                        {
                            "role": "system",
                            "content": (
                                "You judge whether two benchmark evidence items are effectively duplicates. "
                                "Return only YES or NO. "
                                "Answer YES only if they describe the same story, initiative, announcement, or case study angle, "
                                "even if published by different outlets. "
                                "Answer NO if they provide meaningfully different evidence angles."
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                f"Item A title: {existing_title}\n"
                                f"Item A summary: {existing_summary}\n\n"
                                f"Item B title: {candidate_title}\n"
                                f"Item B summary: {candidate_summary}\n\n"
                                "Are these duplicate evidence items?"
                            ),
                        },
                    ]
                )
            except Exception as exc:
                logger.warning("Discovery semantic dedup check failed: %s", exc)
                return False
            decision = normalize_text(str(content or "")).strip().upper()
            if decision.startswith("YES"):
                return True
        return False

    async def _infer_company_domain(self, *, company_name: str, documents: list[dict[str, Any]]) -> str | None:
        if not documents:
            return None
        if self.llm is None:
            for document in documents:
                domain = self._url_domain(str(document.get("url") or ""))
                if domain:
                    return domain
            return None

        domain_lines = []
        seen_domains: set[str] = set()
        for doc in documents[:8]:
            domain = self._url_domain(str(doc.get("url") or ""))
            if not domain or domain in seen_domains:
                continue
            seen_domains.add(domain)
            domain_lines.append(f"- {domain}")
        if not domain_lines:
            return None

        try:
            content = await self.llm.gateway.chat_messages(
                [
                    {
                        "role": "system",
                        "content": (
                            "Choose the most likely official company domain from the provided domains. "
                            "Return only the bare domain or NONE."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Company: {company_name}\n"
                            f"Candidate domains:\n{chr(10).join(domain_lines)}"
                        ),
                    },
                ]
            )
        except Exception as exc:
            logger.warning("Discovery company domain inference failed for %r: %s", company_name, exc)
            return None
        decision = normalize_text(str(content or "")).strip().lower()
        if not decision or decision == "none":
            return None
        decision = decision.split()[0]
        if "." not in decision:
            return None
        return decision

    def _normalize_company_key(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", normalize_text(value).lower())

    def _url_domain(self, url: str) -> str | None:
        match = re.match(r"^https?://([^/]+)", url.strip(), flags=re.IGNORECASE)
        if not match:
            return None
        return match.group(1).lower()
