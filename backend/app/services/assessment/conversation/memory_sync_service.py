from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any

from app.domain.constants import ASSESSMENT_STATUS_IN_PROGRESS
from app.repositories.assessment_axis_memory_repository import AssessmentAxisMemoryRepository
from app.schemas.assessment import NextQuestionResponse
from app.services.llm.core.facade_service import LLMService

logger = logging.getLogger(__name__)


class MemorySyncService:
    """Owns async memory update scheduling, persistence, and task cancellation."""

    def __init__(
        self,
        axis_memory: AssessmentAxisMemoryRepository,
        llm_service: LLMService,
        next_question: Callable[[int], Awaitable[NextQuestionResponse | None]],
    ) -> None:
        self.axis_memory = axis_memory
        self.llm = llm_service
        self._next_question = next_question

    def schedule_next_question_prefetch(
        self,
        assessment: Any,
        assessment_id: int | None = None,
        axis: str | None = None,
        memory_update_task: asyncio.Task[str] | None = None,
    ) -> asyncio.Task[NextQuestionResponse | None] | None:
        if assessment.status != ASSESSMENT_STATUS_IN_PROGRESS:
            return None
        resolved_assessment_id = int(assessment_id or assessment.id)
        if memory_update_task is not None and axis:
            return asyncio.create_task(
                self._prefetch_next_question_after_memory(
                    assessment_id=resolved_assessment_id,
                    axis=axis,
                    memory_update_task=memory_update_task,
                )
            )
        return asyncio.create_task(self._next_question(resolved_assessment_id))

    async def _prefetch_next_question_after_memory(
        self,
        assessment_id: int,
        axis: str,
        memory_update_task: asyncio.Task[str],
    ) -> NextQuestionResponse | None:
        await self.persist_scheduled_axis_memory_update(
            assessment_id=assessment_id,
            axis=axis,
            memory_update_task=memory_update_task,
        )
        return await self._next_question(assessment_id)

    async def schedule_axis_memory_update(
        self,
        assessment_id: int,
        axis: str,
        answer: str,
        covered_ids: list[int],
        axis_capabilities: list[dict],
    ) -> asyncio.Task[str] | None:
        if not answer or not str(answer).strip():
            return None
        is_garbage, garbage_score, reason = self._garbage_signal(answer)
        if is_garbage:
            logger.info(
                "Axis memory update skipped for garbage-like answer (assessment_id=%s, axis=%s, score=%.2f, reason=%s)",
                assessment_id,
                axis,
                garbage_score,
                reason,
            )
            return None

        covered_labels = self.covered_labels_for_memory(
            covered_ids=covered_ids,
            axis_capabilities=axis_capabilities,
        )

        current = await self.axis_memory.get(assessment_id=assessment_id, axis=axis)
        current_summary = current.summary if current is not None else None
        return asyncio.create_task(
            self.llm.update_axis_memory(
                axis=axis,
                current_summary=current_summary,
                new_answer=answer,
                covered_labels=covered_labels,
            )
        )

    def _garbage_signal(self, answer: str) -> tuple[bool, float, str]:
        normalized = re.sub(r"[^\w\s]", " ", str(answer or "").lower())
        normalized = re.sub(r"\s+", " ", normalized).strip()
        if not normalized:
            return True, 1.0, "empty"

        if self._contains_business_allowlist(normalized):
            return False, 0.0, "allowlist_business_signal"

        score = 0.0
        reason = "none"

        if re.search(r"\b(bla\s*bla(?:\s*bla)*)\b", normalized):
            score += 0.75
            reason = "placeholder_bla"
        if re.search(r"\b(blah\s*blah(?:\s*blah)*)\b", normalized):
            score += 0.75
            reason = "placeholder_blah"
        if re.search(r"\b(test(?:\s*test)*)\b", normalized):
            score += 0.55
            reason = "placeholder_test"
        if "lorem ipsum" in normalized:
            score += 1.0
            reason = "placeholder_lorem"

        tokens = normalized.split()
        if len(tokens) >= 3 and len(set(tokens)) == 1:
            score += 0.6
            reason = "repeated_single_token"

        if len(tokens) >= 4:
            short_token_count = sum(1 for token in tokens if len(token) <= 2)
            short_ratio = short_token_count / len(tokens)
            if short_ratio >= 0.75:
                score += 0.35
                reason = "high_short_token_ratio"

        is_garbage = score >= 0.7
        return is_garbage, min(score, 1.0), reason

    def _contains_business_allowlist(self, normalized_text: str) -> bool:
        business_signals = {
            "email",
            "mail",
            "phone",
            "call",
            "whatsapp",
            "excel",
            "crm",
            "jira",
            "trello",
            "nps",
            "kpi",
            "notes",
            "ticket",
            "backlog",
            "survey",
            "complaint",
            "feedback",
            "cx",
            "lead",
            "manager",
            "owner",
            "team",
            "weekly",
            "monthly",
            "ad hoc",
        }
        padded = f" {normalized_text} "
        return any(f" {term} " in padded for term in business_signals)

    async def finalize_parallel_llm_tasks(
        self,
        assessment_id: int,
        axis: str,
        memory_update_task: asyncio.Task[str] | None,
        next_question_task: asyncio.Task[NextQuestionResponse | None] | None,
    ) -> None:
        tasks = [task for task in (memory_update_task, next_question_task) if task is not None]
        if not tasks:
            return

        results = await asyncio.gather(*tasks, return_exceptions=True)
        result_by_task = dict(zip(tasks, results))

        if next_question_task is not None:
            next_question_result = result_by_task.get(next_question_task)
            if isinstance(next_question_result, BaseException):
                logger.error(
                    "Next question prefetch failed for assessment %s: %s",
                    assessment_id,
                    next_question_result,
                    exc_info=(type(next_question_result), next_question_result, next_question_result.__traceback__),
                )

        if memory_update_task is not None and next_question_task is None:
            await self.persist_axis_memory_result(
                assessment_id=assessment_id,
                axis=axis,
                result=result_by_task.get(memory_update_task),
            )

    async def persist_scheduled_axis_memory_update(
        self,
        assessment_id: int,
        axis: str,
        memory_update_task: asyncio.Task[str] | None,
    ) -> None:
        if memory_update_task is None:
            return

        result = (await asyncio.gather(memory_update_task, return_exceptions=True))[0]
        await self.persist_axis_memory_result(assessment_id=assessment_id, axis=axis, result=result)

    async def persist_axis_memory_result(
        self,
        assessment_id: int,
        axis: str,
        result: str | BaseException | None,
    ) -> None:
        if isinstance(result, BaseException):
            logger.error(
                "Axis memory update failed for assessment %s: %s",
                assessment_id,
                result,
                exc_info=(type(result), result, result.__traceback__),
            )
            return

        updated = str(result or "").strip()
        if not updated:
            return
        await self.axis_memory.upsert(assessment_id=assessment_id, axis=axis, summary=updated)

    async def cancel_scheduled_axis_memory_update(self, memory_update_task: asyncio.Task[str] | None) -> None:
        if memory_update_task is None or memory_update_task.done():
            return
        memory_update_task.cancel()
        await asyncio.gather(memory_update_task, return_exceptions=True)

    async def cancel_scheduled_next_question_prefetch(
        self,
        next_question_task: asyncio.Task[NextQuestionResponse | None] | None,
    ) -> None:
        if next_question_task is None or next_question_task.done():
            return
        next_question_task.cancel()
        await asyncio.gather(next_question_task, return_exceptions=True)

    def covered_labels_for_memory(self, covered_ids: list[int], axis_capabilities: list[dict]) -> list[str]:
        covered_set = {int(capability_id) for capability_id in (covered_ids or [])}
        if not covered_set:
            return []

        label_by_id: dict[int, str] = {}
        for row in axis_capabilities or []:
            try:
                capability_id = int(row.get("id"))
            except Exception:
                continue
            label_by_id[capability_id] = str(row.get("label") or "").strip()

        return [label_by_id[capability_id] for capability_id in covered_ids if label_by_id.get(capability_id)]

    async def update_axis_memory(
        self,
        assessment_id: int,
        axis: str,
        answer: str,
        covered_ids: list[int],
        axis_capabilities: list[dict],
    ) -> None:
        memory_update_task = await self.schedule_axis_memory_update(
            assessment_id=assessment_id,
            axis=axis,
            answer=answer,
            covered_ids=covered_ids,
            axis_capabilities=axis_capabilities,
        )
        await self.persist_scheduled_axis_memory_update(
            assessment_id=assessment_id,
            axis=axis,
            memory_update_task=memory_update_task,
        )


def build_memory_sync_service(
    axis_memory: AssessmentAxisMemoryRepository,
    llm_service: LLMService,
    next_question: Callable[[int], Awaitable[NextQuestionResponse | None]],
) -> MemorySyncService:
    return MemorySyncService(
        axis_memory=axis_memory,
        llm_service=llm_service,
        next_question=next_question,
    )
