"""What happens when the client sends an answer during the guided diagnostic.

This is the write half of the conversation loop (`question_flow_service` is the read half). One
submitted answer runs through: classify what the client actually did, score it against the
capability rubrics if it is a real answer, persist, and decide what the conversation does next.

Most of the size is the **non-answer cases**, and that is the point. A guided diagnostic has to
cope with a client who asks to resume later, misunderstands the question twice in a row, or keeps
giving answers too thin to score. Each of those has its own handler and its own bounded retry
count, so the conversation always makes progress instead of looping -- the limits live in
`Settings` (`chat_max_clarifications_per_focus`, `chat_max_insufficient_evidence_retries`).
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable
from typing import Any

from app.core.text_normalization import normalize_text
from app.domain.constants import ASSESSMENT_STATUS_IN_PROGRESS
from app.repositories.assessment_answer_repository import AssessmentAnswerRepository
from app.repositories.assessment_repository import AssessmentRepository
from app.repositories.capability_repository import CapabilityRepository
from app.schemas.assessment import AnswerResponse, NextQuestionResponse
from app.services.assessment.conversation.question_flow_service import QuestionFlowService
from app.services.assessment.reporting.reporting_service import AssessmentReportingService
from app.services.assessment.scoring.scoring_service import AssessmentScoringService
from app.services.assessment.state.state_service import AssessmentStateService
from app.services.llm.core.facade_service import LLMService


class AnswerFlowService:
    """Owns submit-answer routing, scoring integration, and persistence."""

    def __init__(
        self,
        assessments: AssessmentRepository,
        capabilities: CapabilityRepository,
        answers: AssessmentAnswerRepository,
        llm_service: LLMService,
        state_service: AssessmentStateService,
        scoring_service: AssessmentScoringService,
        reporting_service: AssessmentReportingService,
        question_flow_service: QuestionFlowService,
        max_extra_questions_per_axis: Callable[[], int],
        max_clarifications_per_focus: Callable[[], int],
        max_insufficient_evidence_retries: Callable[[], int],
        schedule_axis_memory_update: Callable[[int, str, str, list[int], list[dict]], Awaitable[asyncio.Task[str] | None]],
        schedule_next_question_prefetch: Callable[
            [Any, int | None, str | None, asyncio.Task[str] | None],
            asyncio.Task[NextQuestionResponse | None] | None,
        ],
        cancel_scheduled_axis_memory_update: Callable[[asyncio.Task[str] | None], Awaitable[None]],
        cancel_scheduled_next_question_prefetch: Callable[[asyncio.Task[NextQuestionResponse | None] | None], Awaitable[None]],
        finalize_parallel_llm_tasks: Callable[[int, str, asyncio.Task[str] | None, asyncio.Task[NextQuestionResponse | None] | None], Awaitable[None]],
    ) -> None:
        self.assessments = assessments
        self.capabilities = capabilities
        self.answers = answers
        self.llm = llm_service
        self.state = state_service
        self.scoring = scoring_service
        self.reporting = reporting_service
        self.question_flow = question_flow_service
        self._max_extra_questions_per_axis = max_extra_questions_per_axis
        self._max_clarifications_per_focus = max_clarifications_per_focus
        self._max_insufficient_evidence_retries = max_insufficient_evidence_retries
        self._schedule_axis_memory_update = schedule_axis_memory_update
        self._schedule_next_question_prefetch = schedule_next_question_prefetch
        self._cancel_scheduled_axis_memory_update = cancel_scheduled_axis_memory_update
        self._cancel_scheduled_next_question_prefetch = cancel_scheduled_next_question_prefetch
        self._finalize_parallel_llm_tasks = finalize_parallel_llm_tasks

    async def submit_answer(
        self,
        assessment_id: int,
        answer: str,
        expected_axis: str | None = None,
        expected_version: int | None = None,
    ) -> AnswerResponse | None:
        assessment = await self.assessments.get_by_id_for_update(assessment_id)
        if assessment is None:
            return None

        self.state.assert_expected_state(
            assessment=assessment,
            expected_axis=expected_axis,
            expected_version=expected_version,
        )

        status_response = await self.state.ensure_assessment_still_active(
            assessment_id=assessment_id,
            assessment=assessment,
            max_extra_questions_per_axis=self._max_extra_questions_per_axis(),
        )
        if status_response is not None:
            return AnswerResponse(status=assessment.status, axis=None, covered=[], confidence=None)

        axis = self.state.current_axis_name(assessment)
        axis_capabilities = await self.capabilities.list_for_axis(assessment_id, axis)
        intent = await self.llm.route_user_intent(
            answer,
            previous_question=(assessment.pending_question or "").strip() or None,
        )
        if intent != "VALID_ANSWER" and self._matches_pending_option_answer(assessment, answer):
            intent = "VALID_ANSWER"

        if intent == "VALID_ANSWER":
            return await self.process_valid_answer(
                assessment_id=assessment_id,
                assessment=assessment,
                axis=axis,
                answer=answer,
                axis_capabilities=axis_capabilities,
            )

        if intent == "RESUME":
            return await self.handle_resume_intent(
                assessment_id=assessment_id,
                assessment=assessment,
                axis=axis,
                answer=answer,
                axis_capabilities=axis_capabilities,
            )

        return await self.handle_non_valid_intent(
            assessment_id=assessment_id,
            assessment=assessment,
            axis=axis,
            answer=answer,
            axis_capabilities=axis_capabilities,
            intent=intent,
        )

    async def process_valid_answer(
        self,
        assessment_id: int,
        assessment: Any,
        axis: str,
        answer: str,
        axis_capabilities: list[dict],
    ) -> AnswerResponse:
        active_focus_capability_id = self.question_flow.resolve_pending_focus_capability_id(assessment)
        focus = self.question_flow.select_question_focus(
            axis=axis,
            axis_capabilities=axis_capabilities,
            active_focus_capability_id=active_focus_capability_id,
        )
        axis_capability_ids = [int(c["id"]) for c in axis_capabilities if "id" in c]
        all_rubrics_by_capability = await self.capabilities.get_rubrics_for_capabilities(axis_capability_ids)
        coverage_candidates = self._coverage_candidates_for_answer(
            axis_capabilities=axis_capabilities,
            focus_capability_id=focus.get("primary_capability_id"),
            answer=answer,
            rubrics_by_capability=all_rubrics_by_capability,
        )
        capability_ids = [int(c["id"]) for c in coverage_candidates if "id" in c]
        rubrics_by_capability = {
            capability_id: all_rubrics_by_capability.get(capability_id, [])
            for capability_id in capability_ids
        }
        coverage = await self.llm.detect_coverage(
            answer=answer,
            criteria=coverage_candidates,
            rubrics_by_capability=rubrics_by_capability,
        )

        covered_ids = coverage.get("covered") or []
        covered_ids = self.scoring.apply_followup_gating(
            covered_ids=covered_ids,
            confidence_by_id=coverage.get("confidence_by_id") or {},
            evidence_by_id=coverage.get("evidence_by_id") or {},
            rationale_by_id=coverage.get("rationale_by_id") or {},
            maturity_level_number_by_id=coverage.get("maturity_level_number_by_id") or {},
            is_specific_and_actionable_by_id=coverage.get("is_specific_and_actionable_by_id") or {},
        )
        if (
            not covered_ids
            and self.llm.is_negative_evidence_answer(answer)
            and self._is_generic_negative_evidence_answer(answer)
        ):
            covered_ids = await self._force_level_one_for_current_focus(
                coverage=coverage,
                focus_capability_id=focus.get("primary_capability_id"),
                answer=answer,
                rationale=self._negative_evidence_rationale(answer),
                evidence=self._negative_evidence_evidence(answer),
            )
        if self._should_request_maturity_confirmation_followup(
            assessment=assessment,
            coverage=coverage,
            covered_ids=covered_ids,
            focus_capability_id=focus.get("primary_capability_id"),
            answer=answer,
        ):
            return await self.request_maturity_confirmation_followup(
                assessment_id=assessment_id,
                assessment=assessment,
                answer=answer,
                axis_capabilities=axis_capabilities,
                focus_capability_id=int(focus["primary_capability_id"]),
            )
        confidence = self.scoring.resolve_confidence(covered_ids=covered_ids, confidence=coverage.get("confidence"))
        memory_update_task = await self._schedule_axis_memory_update(
            assessment_id=assessment_id,
            axis=axis,
            answer=answer,
            covered_ids=covered_ids,
            axis_capabilities=axis_capabilities,
        )
        next_question_task: asyncio.Task[NextQuestionResponse | None] | None = None
        try:
            await self.scoring.persist_scoring(
                assessment_id=assessment_id,
                covered_ids=covered_ids,
                confidence=confidence,
                maturity_level_by_id=coverage.get("maturity_level_by_id") or {},
                rationale_by_id=coverage.get("rationale_by_id") or {},
            )
            await self.scoring.persist_insights(
                assessment_id=assessment_id,
                covered_ids=covered_ids,
                maturity_level_by_id=coverage.get("maturity_level_by_id") or {},
                confidence=confidence,
                rationale_by_id=coverage.get("rationale_by_id") or {},
                evidence_by_id=coverage.get("evidence_by_id") or {},
            )
            await self.persist_answer(
                assessment_id=assessment_id,
                answer=answer,
                covered_ids=covered_ids,
                axis_capabilities=axis_capabilities,
                question_text=(assessment.pending_question or "").strip() or None,
                fallback_capability_id=focus.get("primary_capability_id"),
            )
            await self.update_assessment_after_valid_answer(
                assessment_id=assessment_id,
                assessment=assessment,
                covered_ids=covered_ids,
                focus_capability_id=focus.get("primary_capability_id"),
            )
            next_question_task = self._schedule_next_question_prefetch(
                assessment,
                assessment_id,
                axis,
                memory_update_task,
            )
        except Exception:
            await self._cancel_scheduled_axis_memory_update(memory_update_task)
            await self.expected_evidence_cancel_scheduled_next_question_prefetch(next_question_task)
            raise
        await self._finalize_parallel_llm_tasks(
            assessment_id=assessment_id,
            axis=axis,
            memory_update_task=memory_update_task,
            next_question_task=next_question_task,
        )
        return AnswerResponse(
            status=assessment.status,
            axis=self.state.response_axis(assessment),
            covered=covered_ids,
            confidence=float(confidence),
        )

    async def update_assessment_after_valid_answer(
        self,
        assessment_id: int,
        assessment: Any,
        covered_ids: list[int],
        focus_capability_id: int | None,
    ) -> None:
        prior_clarification_count = int(assessment.clarification_count or 0)
        assessment.pending_question = None
        assessment.pending_options = None
        if covered_ids:
            assessment.pending_followup_hint = None
            assessment.pending_focus_capability_id = None
            assessment.clarification_count = 0
        else:
            assessment.pending_followup_hint = (
                self.question_flow.set_followup_hint("insufficient_evidence", focus_capability_id)
                if prior_clarification_count < self._max_insufficient_evidence_retries()
                else None
            )
            assessment.pending_focus_capability_id = focus_capability_id
            assessment.clarification_count = prior_clarification_count + 1
        assessment.current_axis_question_count = int(assessment.current_axis_question_count) + 1
        await self.state.advance_if_axis_complete(
            assessment_id=assessment_id,
            assessment=assessment,
            max_extra_questions_per_axis=self._max_extra_questions_per_axis(),
        )
        self.state.bump_version(assessment)

    async def handle_resume_intent(
        self,
        assessment_id: int,
        assessment: Any,
        axis: str,
        answer: str,
        axis_capabilities: list[dict],
    ) -> AnswerResponse:
        focus = self.question_flow.select_question_focus(
            axis=axis,
            axis_capabilities=axis_capabilities,
            active_focus_capability_id=self.question_flow.resolve_pending_focus_capability_id(assessment),
        )
        focus_capability_id = focus.get("primary_capability_id")
        if focus_capability_id is None:
            return await self.record_non_scoring_turn(
                assessment_id=assessment_id,
                assessment=assessment,
                answer=answer,
                axis_capabilities=axis_capabilities,
                pending_followup_hint=None,
                clear_pending_question=True,
            )

        level_one = await self.assessments.get_maturity_level_by_number(1)
        maturity_level_id = int(level_one.id) if level_one is not None else None
        confidence = self.scoring.resolve_confidence(covered_ids=[int(focus_capability_id)], confidence=None)
        rationale = self._resume_rationale(answer)
        evidence = self._resume_evidence(answer)

        await self.scoring.persist_scoring(
            assessment_id=assessment_id,
            covered_ids=[int(focus_capability_id)],
            confidence=confidence,
            maturity_level_by_id={int(focus_capability_id): maturity_level_id} if maturity_level_id is not None else {},
            rationale_by_id={int(focus_capability_id): rationale},
        )
        await self.scoring.persist_insights(
            assessment_id=assessment_id,
            covered_ids=[int(focus_capability_id)],
            maturity_level_by_id={int(focus_capability_id): maturity_level_id} if maturity_level_id is not None else {},
            confidence=confidence,
            rationale_by_id={int(focus_capability_id): rationale},
            evidence_by_id={int(focus_capability_id): evidence},
        )
        await self.persist_answer(
            assessment_id=assessment_id,
            answer=answer,
            covered_ids=[int(focus_capability_id)],
            axis_capabilities=axis_capabilities,
            question_text=(assessment.pending_question or "").strip() or None,
            fallback_capability_id=int(focus_capability_id),
        )
        await self.update_assessment_after_valid_answer(
            assessment_id=assessment_id,
            assessment=assessment,
            covered_ids=[int(focus_capability_id)],
            focus_capability_id=int(focus_capability_id),
        )
        next_question_task = self._schedule_next_question_prefetch(assessment, assessment_id, axis, None)
        await self._finalize_parallel_llm_tasks(
            assessment_id=assessment_id,
            axis=axis,
            memory_update_task=None,
            next_question_task=next_question_task,
        )
        return AnswerResponse(
            status=assessment.status,
            axis=self.state.response_axis(assessment),
            covered=[int(focus_capability_id)],
            confidence=float(confidence),
        )

    async def handle_non_valid_intent(
        self,
        assessment_id: int,
        assessment: Any,
        axis: str,
        answer: str,
        axis_capabilities: list[dict],
        intent: str,
    ) -> AnswerResponse:
        if intent == "CONFUSION" and self._should_exit_repeated_confusion(assessment):
            return await self.handle_repeated_confusion_intent(
                assessment_id=assessment_id,
                assessment=assessment,
                axis=axis,
                answer=answer,
                axis_capabilities=axis_capabilities,
            )

        if intent == "LOW_QUALITY" and self._should_exit_repeated_low_quality(assessment):
            return await self.handle_repeated_low_quality_intent(
                assessment_id=assessment_id,
                assessment=assessment,
                axis=axis,
                answer=answer,
                axis_capabilities=axis_capabilities,
            )

        previous_question = (assessment.pending_question or "").strip() or None
        await self.persist_answer(
            assessment_id=assessment_id,
            answer=answer,
            covered_ids=[],
            axis_capabilities=axis_capabilities,
            question_text=previous_question,
            fallback_capability_id=self.question_flow.resolve_pending_focus_capability_id(assessment),
        )
        clarification_question = await self.question_flow.generate_intent_clarification_question(
            assessment_id=assessment_id,
            axis=axis,
            answer=answer,
            axis_capabilities=axis_capabilities,
            intent=intent,
            previous_question=previous_question,
        )
        if intent == "LOW_QUALITY":
            clarification_question = self._build_low_quality_clarification_message(
                clarification_question,
                low_quality_count=int(assessment.current_axis_low_quality_count or 0) + 1,
                language=getattr(assessment, "language", "fr"),
            )

        if intent == "LOW_QUALITY":
            assessment.current_axis_low_quality_count = int(assessment.current_axis_low_quality_count or 0) + 1

        pending_focus_capability_id = self.question_flow.resolve_pending_focus_capability_id(assessment)
        pending_options = await self.question_flow.options_for_focus(
            pending_focus_capability_id,
            language=getattr(assessment, "language", "fr"),
        )
        assessment.pending_question = None
        assessment.pending_options = None
        assessment.pending_followup_hint = None
        assessment.pending_focus_capability_id = None
        is_same_active_axis = (
            assessment.status == ASSESSMENT_STATUS_IN_PROGRESS
            and self.state.current_axis_name(assessment) == axis
        )
        assessment.clarification_count = (
            self.next_clarification_count(assessment=assessment, intent=intent)
            if is_same_active_axis
            else 0
        )
        if is_same_active_axis:
            assessment.pending_question = clarification_question
            assessment.pending_options = pending_options
            assessment.pending_focus_capability_id = pending_focus_capability_id
            assessment.conversation_stage = "diagnostic"

        self.state.bump_version(assessment)
        return AnswerResponse(
            status=assessment.status,
            axis=self.state.response_axis(assessment),
            covered=[],
            confidence=0.0,
        )

    async def handle_repeated_confusion_intent(
        self,
        assessment_id: int,
        assessment: Any,
        axis: str,
        answer: str,
        axis_capabilities: list[dict],
    ) -> AnswerResponse:
        focus = self.question_flow.select_question_focus(
            axis=axis,
            axis_capabilities=axis_capabilities,
            active_focus_capability_id=self.question_flow.resolve_pending_focus_capability_id(assessment),
        )
        focus_capability_id = focus.get("primary_capability_id")
        if focus_capability_id is None:
            return await self.record_non_scoring_turn(
                assessment_id=assessment_id,
                assessment=assessment,
                answer=answer,
                axis_capabilities=axis_capabilities,
                pending_followup_hint=None,
                clear_pending_question=True,
                increment_clarification=True,
            )

        capability_id = int(focus_capability_id)
        level_one = await self.assessments.get_maturity_level_by_number(1)
        maturity_level_id = int(level_one.id) if level_one is not None else None
        confidence = self.scoring.resolve_confidence(covered_ids=[capability_id], confidence=None)
        rationale = self._confusion_exit_rationale(answer)
        evidence = self._confusion_exit_evidence(answer)

        await self.scoring.persist_scoring(
            assessment_id=assessment_id,
            covered_ids=[capability_id],
            confidence=confidence,
            maturity_level_by_id={capability_id: maturity_level_id} if maturity_level_id is not None else {},
            rationale_by_id={capability_id: rationale},
        )
        await self.scoring.persist_insights(
            assessment_id=assessment_id,
            covered_ids=[capability_id],
            maturity_level_by_id={capability_id: maturity_level_id} if maturity_level_id is not None else {},
            confidence=confidence,
            rationale_by_id={capability_id: rationale},
            evidence_by_id={capability_id: evidence},
        )
        await self.persist_answer(
            assessment_id=assessment_id,
            answer=answer,
            covered_ids=[capability_id],
            axis_capabilities=axis_capabilities,
            question_text=(assessment.pending_question or "").strip() or None,
            fallback_capability_id=capability_id,
        )
        await self.update_assessment_after_valid_answer(
            assessment_id=assessment_id,
            assessment=assessment,
            covered_ids=[capability_id],
            focus_capability_id=capability_id,
        )
        assessment.pending_followup_hint = self.question_flow.set_followup_hint("low_quality_exit", capability_id)
        next_question_task = self._schedule_next_question_prefetch(assessment, assessment_id, axis, None)
        await self._finalize_parallel_llm_tasks(
            assessment_id=assessment_id,
            axis=axis,
            memory_update_task=None,
            next_question_task=next_question_task,
        )
        return AnswerResponse(
            status=assessment.status,
            axis=self.state.response_axis(assessment),
            covered=[capability_id],
            confidence=float(confidence),
        )

    async def handle_repeated_low_quality_intent(
        self,
        assessment_id: int,
        assessment: Any,
        axis: str,
        answer: str,
        axis_capabilities: list[dict],
    ) -> AnswerResponse:
        focus = self.question_flow.select_question_focus(
            axis=axis,
            axis_capabilities=axis_capabilities,
            active_focus_capability_id=self.question_flow.resolve_pending_focus_capability_id(assessment),
        )
        focus_capability_id = focus.get("primary_capability_id")
        if focus_capability_id is None:
            return await self.record_non_scoring_turn(
                assessment_id=assessment_id,
                assessment=assessment,
                answer=answer,
                axis_capabilities=axis_capabilities,
                pending_followup_hint=None,
                clear_pending_question=True,
                increment_clarification=True,
                increment_low_quality=True,
            )

        capability_id = int(focus_capability_id)
        level_one = await self.assessments.get_maturity_level_by_number(1)
        maturity_level_id = int(level_one.id) if level_one is not None else None
        confidence = self.scoring.resolve_confidence(covered_ids=[capability_id], confidence=None)
        rationale = self._low_quality_exit_rationale(answer)
        evidence = self._low_quality_exit_evidence(answer)

        assessment.current_axis_low_quality_count = int(assessment.current_axis_low_quality_count or 0) + 1
        await self.scoring.persist_scoring(
            assessment_id=assessment_id,
            covered_ids=[capability_id],
            confidence=confidence,
            maturity_level_by_id={capability_id: maturity_level_id} if maturity_level_id is not None else {},
            rationale_by_id={capability_id: rationale},
        )
        await self.scoring.persist_insights(
            assessment_id=assessment_id,
            covered_ids=[capability_id],
            maturity_level_by_id={capability_id: maturity_level_id} if maturity_level_id is not None else {},
            confidence=confidence,
            rationale_by_id={capability_id: rationale},
            evidence_by_id={capability_id: evidence},
        )
        await self.persist_answer(
            assessment_id=assessment_id,
            answer=answer,
            covered_ids=[capability_id],
            axis_capabilities=axis_capabilities,
            question_text=(assessment.pending_question or "").strip() or None,
            fallback_capability_id=capability_id,
        )
        await self.update_assessment_after_valid_answer(
            assessment_id=assessment_id,
            assessment=assessment,
            covered_ids=[capability_id],
            focus_capability_id=capability_id,
        )
        assessment.pending_followup_hint = self.question_flow.set_followup_hint("low_quality_exit", capability_id)
        next_question_task = self._schedule_next_question_prefetch(assessment, assessment_id, axis, None)
        await self._finalize_parallel_llm_tasks(
            assessment_id=assessment_id,
            axis=axis,
            memory_update_task=None,
            next_question_task=next_question_task,
        )
        return AnswerResponse(
            status=assessment.status,
            axis=self.state.response_axis(assessment),
            covered=[capability_id],
            confidence=float(confidence),
        )

    def next_clarification_count(self, assessment: Any, intent: str) -> int:
        return int(assessment.clarification_count or 0) + 1

    def _matches_pending_option_answer(self, assessment: Any, answer: str) -> bool:
        pending_options = getattr(assessment, "pending_options", None) or []
        if not pending_options:
            return False

        normalized_answer = self._normalize_option_text(answer)
        if not normalized_answer:
            return False

        for option in pending_options:
            if normalized_answer == self._normalize_option_text(option):
                return True
        return False

    def _normalize_option_text(self, value: Any) -> str:
        return normalize_text(str(value or "")).strip().lower()

    def _should_exit_repeated_low_quality(self, assessment: Any) -> bool:
        threshold = 3
        return int(assessment.current_axis_low_quality_count or 0) + 1 >= threshold

    def _should_exit_repeated_confusion(self, assessment: Any) -> bool:
        return int(assessment.clarification_count or 0) + 1 > self._max_clarifications_per_focus()

    def _should_request_maturity_confirmation_followup(
        self,
        assessment: Any,
        coverage: dict,
        covered_ids: list[int],
        focus_capability_id: int | None,
        answer: str,
    ) -> bool:
        if focus_capability_id is None or int(focus_capability_id) not in {int(item) for item in covered_ids}:
            return False
        if self.llm.is_negative_evidence_answer(answer):
            return False
        if self.question_flow.extract_followup_hint(assessment.pending_followup_hint) == "maturity_confirmation":
            return False
        if int(assessment.clarification_count or 0) >= self._max_clarifications_per_focus():
            return False

        capability_id = int(focus_capability_id)
        maturity_level = int((coverage.get("maturity_level_number_by_id") or {}).get(capability_id, 0) or 0)
        if maturity_level < 2:
            return False

        confidence = float((coverage.get("confidence_by_id") or {}).get(capability_id, coverage.get("confidence") or 0.0) or 0.0)
        is_specific_and_actionable = bool(
            (coverage.get("is_specific_and_actionable_by_id") or {}).get(capability_id, False)
        )
        evidence = normalize_text((coverage.get("evidence_by_id") or {}).get(capability_id, ""))
        rationale = normalize_text((coverage.get("rationale_by_id") or {}).get(capability_id, ""))
        return self._looks_like_promising_but_incomplete_signal(
            confidence=confidence,
            is_specific_and_actionable=is_specific_and_actionable,
            evidence=evidence,
            rationale=rationale,
        )

    def _looks_like_promising_but_incomplete_signal(
        self,
        confidence: float,
        is_specific_and_actionable: bool,
        evidence: str,
        rationale: str,
    ) -> bool:
        if is_specific_and_actionable:
            return False

        if confidence < 0.6:
            return False

        if confidence < 0.8:
            return True

        combined = f"{evidence} {rationale}".lower()
        uncertainty_markers = (
            "partial",
            "inconsistent",
            "limited",
            "not systematic",
            "uneven",
        )
        return any(marker in combined for marker in uncertainty_markers)

    def _build_low_quality_clarification_message(self, clarification_question: str, low_quality_count: int, language: str = "fr") -> str:
        question_text = (clarification_question or "").strip()
        if not question_text:
            question_text = (
                "Could you restate your answer in one clear business sentence?"
                if language == "en"
                else "Pourriez-vous reformuler votre réponse en une phrase claire sur votre activité ?"
            )

        if low_quality_count <= 1:
            prefix = (
                "I didn't understand your last answer, and it doesn't give me a clear business signal."
                if language == "en"
                else "Je n'ai pas compris votre dernière réponse, et elle ne me donne pas de signal clair."
            )
        elif low_quality_count == 2:
            prefix = (
                "That still does not give me a usable business signal."
                if language == "en"
                else "Cela ne me donne toujours pas de signal clair."
            )
        else:
            prefix = (
                "I still cannot interpret that answer, so I will move on and continue the assessment."
                if language == "en"
                else "Je n'arrive toujours pas à interpréter cette réponse, je vais donc passer à la suite de l'évaluation."
            )

        return f"{prefix} {question_text}"

    async def _force_level_one_for_current_focus(
        self,
        coverage: dict,
        focus_capability_id: int | None,
        answer: str,
        rationale: str,
        evidence: str,
    ) -> list[int]:
        if focus_capability_id is None:
            return []

        capability_id = int(focus_capability_id)
        level_one = await self.assessments.get_maturity_level_by_number(1)
        maturity_level_id = int(level_one.id) if level_one is not None else None
        confidence = self.scoring.resolve_confidence(covered_ids=[capability_id], confidence=None)

        coverage["covered"] = [capability_id]
        coverage["confidence"] = confidence
        coverage["confidence_by_id"] = {capability_id: confidence}
        coverage["maturity_level_number_by_id"] = {capability_id: 1}
        coverage["maturity_level_by_id"] = {capability_id: maturity_level_id} if maturity_level_id is not None else {}
        coverage["rationale_by_id"] = {capability_id: rationale}
        coverage["evidence_by_id"] = {capability_id: evidence}
        coverage["is_specific_and_actionable_by_id"] = {capability_id: True}
        return [capability_id]

    def _is_generic_negative_evidence_answer(self, answer: str) -> bool:
        normalized = self._normalize_business_text(answer)
        if not normalized:
            return True

        tokens = re.findall(r"[a-z0-9]+", normalized)
        important_terms = self._important_terms(normalized)
        if len(tokens) <= 8 and len(important_terms) <= 2:
            return True
        if len(tokens) <= 5:
            return True
        return False

    def _negative_evidence_rationale(self, answer: str, language: str = "fr") -> str:
        if language == "en":
            return (
                "The user explicitly stated they do not know, have no answer, or lack the process; "
                f"this is recorded as Level 1 maturity evidence. User wording: {self._compact_answer_excerpt(answer)}"
            )
        return (
            "L'utilisateur a explicitement déclaré qu'il ne sait pas, n'a pas de réponse ou n'a pas de processus en place ; "
            f"ceci est enregistré comme un niveau de maturité 1. Formulation de l'utilisateur : {self._compact_answer_excerpt(answer)}"
        )

    def _negative_evidence_evidence(self, answer: str, language: str = "fr") -> str:
        return (
            f"User explicitly stated lack of knowledge or process: {self._compact_answer_excerpt(answer)}"
            if language == "en"
            else f"L'utilisateur a explicitement mentionné un manque de connaissances ou de processus : {self._compact_answer_excerpt(answer)}"
        )

    def _resume_rationale(self, answer: str, language: str = "fr") -> str:
        if language == "en":
            return (
                "The user explicitly asked to skip, pass, or move on before providing assessable evidence; "
                f"this is recorded as Level 1 maturity evidence for the current capability. User wording: {self._compact_answer_excerpt(answer)}"
            )
        return (
            "L'utilisateur a explicitement demandé à passer à la suite sans fournir de preuves tangibles ; "
            f"ceci est enregistré comme un niveau de maturité 1 pour cette capacité. Formulation de l'utilisateur : {self._compact_answer_excerpt(answer)}"
        )

    def _resume_evidence(self, answer: str, language: str = "fr") -> str:
        return (
            f"User explicitly asked to skip or move on: {self._compact_answer_excerpt(answer)}"
            if language == "en"
            else f"L'utilisateur a explicitement demandé à passer ou à continuer : {self._compact_answer_excerpt(answer)}"
        )

    def _low_quality_exit_rationale(self, answer: str, language: str = "fr") -> str:
        if language == "en":
            return (
                "The user repeatedly provided text that could not be interpreted as credible business evidence; "
                f"this is recorded as Level 1 maturity evidence rather than inventing details. User wording: {self._compact_answer_excerpt(answer)}"
            )
        return (
            "L'utilisateur a fourni à plusieurs reprises du texte ne pouvant être interprété comme une preuve commerciale crédible ; "
            f"ceci est enregistré comme un niveau de maturité 1 plutôt que d'inventer des détails. Formulation de l'utilisateur : {self._compact_answer_excerpt(answer)}"
        )



    def _low_quality_exit_evidence(self, answer: str, language: str = "fr") -> str:
        return (
            f"Repeated low-quality or non-interpretable response: {self._compact_answer_excerpt(answer)}"
            if language == "en"
            else f"Réponse répétée de faible qualité ou non interprétable : {self._compact_answer_excerpt(answer)}"
        )

    def _confusion_exit_rationale(self, answer: str, language: str = "fr") -> str:
        if language == "en":
            return (
                "The user repeatedly asked for clarification and did not provide assessable business evidence; "
                f"this is recorded as Level 1 maturity evidence rather than inventing details. User wording: {self._compact_answer_excerpt(answer)}"
            )
        return (
            "L'utilisateur a demandé des clarifications à plusieurs reprises et n'a pas fourni de preuves tangibles ; "
            f"ceci est enregistré comme un niveau de maturité 1 plutôt que d'inventer des détails. Formulation de l'utilisateur : {self._compact_answer_excerpt(answer)}"
        )

    def _confusion_exit_evidence(self, answer: str, language: str = "fr") -> str:
        return (
            f"Repeated clarification request without assessable evidence: {self._compact_answer_excerpt(answer)}"
            if language == "en"
            else f"Demande de clarification répétée sans preuve tangible : {self._compact_answer_excerpt(answer)}"
        )

    def _compact_answer_excerpt(self, answer: str) -> str:
        value = " ".join(str(answer or "").strip().split())
        if not value:
            return '"no answer provided"'
        if len(value) <= 160:
            return f'"{value}"'
        return f'"{value[:157].rstrip()}..."'

    def _coverage_candidates_for_answer(
        self,
        axis_capabilities: list[dict],
        focus_capability_id: int | None,
        answer: str,
        rubrics_by_capability: dict[int, list[dict]] | None = None,
    ) -> list[dict]:
        if not axis_capabilities:
            return []

        primary = self._capability_row_by_id(axis_capabilities, focus_capability_id)
        if primary is None:
            primary = next((row for row in axis_capabilities if not row.get("covered")), axis_capabilities[0])

        candidates: list[dict] = [primary]
        primary_id = self._row_capability_id(primary)
        distinctive_terms_by_id = self._distinctive_profile_terms_by_capability(
            axis_capabilities=axis_capabilities,
            rubrics_by_capability=rubrics_by_capability or {},
        )
        for row in axis_capabilities:
            row_id = self._row_capability_id(row)
            if row_id is None or row_id == primary_id or row.get("covered"):
                continue
            if self._secondary_capability_is_relevant(
                capability=row,
                answer=answer,
                rubrics=(rubrics_by_capability or {}).get(row_id, []),
                distinctive_terms=distinctive_terms_by_id.get(row_id, set()),
            ):
                candidates.append(row)
        return candidates

    def _capability_row_by_id(self, axis_capabilities: list[dict], capability_id: int | None) -> dict | None:
        if capability_id is None:
            return None
        for row in axis_capabilities:
            if self._row_capability_id(row) == int(capability_id):
                return row
        return None

    def _row_capability_id(self, row: dict) -> int | None:
        try:
            value = row.get("id")
            return int(value) if value is not None else None
        except Exception:
            return None

    def _secondary_capability_is_relevant(
        self,
        capability: dict,
        answer: str,
        rubrics: list[dict] | None = None,
        distinctive_terms: set[str] | None = None,
    ) -> bool:
        normalized_answer = self._normalize_business_text(answer)
        if not normalized_answer:
            return False

        answer_terms = self._answer_terms(normalized_answer)
        if not answer_terms:
            return False

        if answer_terms.intersection(distinctive_terms or set()):
            return True

        evidence_phrases = self._split_profile_phrases(str(capability.get("expected_evidence") or ""))
        if any(self._profile_phrase_matches_answer(phrase, answer_terms) for phrase in evidence_phrases):
            return True

        profile_terms = self._capability_profile_terms(capability=capability, rubrics=rubrics or [])
        overlap = answer_terms.intersection(profile_terms)
        if len(answer_terms) <= 3:
            return len(overlap) >= 2 and len(overlap) == len(answer_terms)

        overlap_ratio = len(overlap) / max(min(len(answer_terms), len(profile_terms)), 1)
        return len(overlap) >= 2 and overlap_ratio >= 0.34

    def _normalize_business_text(self, value: str) -> str:
        normalized = re.sub(r"[^\w\s/-]", " ", str(value or "").lower())
        return re.sub(r"\s+", " ", normalized).strip()

    def _answer_terms(self, normalized_answer: str) -> set[str]:
        return self._important_terms(normalized_answer)

    def _important_terms(self, value: str) -> set[str]:
        stopwords = {
            "and",
            "the",
            "for",
            "with",
            "from",
            "that",
            "this",
            "how",
            "what",
            "when",
            "where",
            "which",
            "customer",
            "customers",
            "issue",
            "issues",
            "feedback",
            "process",
            "team",
            "teams",
            "use",
            "uses",
            "used",
            "using",
            "based",
        }
        tokens = re.findall(r"[a-z0-9]+", self._normalize_business_text(value))
        return {
            token
            for token in tokens
            if len(token) >= 3 and token not in stopwords
        }

    def _split_profile_phrases(self, text: str) -> list[str]:
        raw_items = re.split(r"[,;\n.]+", text or "")
        phrases: list[str] = []
        for item in raw_items:
            phrase = self._normalize_business_text(item)
            terms = self._important_terms(phrase)
            if not phrase or not terms:
                continue
            phrases.append(phrase)
        return phrases

    def _profile_phrase_matches_answer(self, phrase: str, answer_terms: set[str]) -> bool:
        phrase_terms = self._important_terms(phrase)
        if not phrase_terms:
            return False
        if len(phrase_terms) == 1:
            return next(iter(phrase_terms)) in answer_terms
        return phrase_terms.issubset(answer_terms)

    def _capability_profile_terms(self, capability: dict, rubrics: list[dict]) -> set[str]:
        chunks = [
            str(capability.get("label") or ""),
            str(capability.get("code") or "").replace("_", " "),
            str(capability.get("description") or ""),
            str(capability.get("expected_evidence") or ""),
        ]
        return self._important_terms(" ".join(chunks))

    def _distinctive_profile_terms_by_capability(
        self,
        axis_capabilities: list[dict],
        rubrics_by_capability: dict[int, list[dict]],
    ) -> dict[int, set[str]]:
        terms_by_id: dict[int, set[str]] = {}
        frequency: dict[str, int] = {}
        for row in axis_capabilities:
            capability_id = self._row_capability_id(row)
            if capability_id is None:
                continue
            terms = self._capability_profile_terms(
                capability=row,
                rubrics=rubrics_by_capability.get(capability_id, []),
            )
            terms_by_id[capability_id] = terms
            for term in terms:
                frequency[term] = frequency.get(term, 0) + 1

        return {
            capability_id: {term for term in terms if frequency.get(term, 0) == 1}
            for capability_id, terms in terms_by_id.items()
        }

    async def record_non_scoring_turn(
        self,
        assessment_id: int,
        assessment: Any,
        answer: str,
        axis_capabilities: list[dict],
        pending_followup_hint: str | None,
        clear_pending_question: bool,
        pending_focus_capability_id: int | None = None,
        increment_clarification: bool = False,
        increment_question_count: bool = False,
        increment_low_quality: bool = False,
    ) -> AnswerResponse:
        await self.persist_answer(
            assessment_id=assessment_id,
            answer=answer,
            covered_ids=[],
            axis_capabilities=axis_capabilities,
            question_text=(assessment.pending_question or "").strip() or None,
            fallback_capability_id=pending_focus_capability_id,
        )
        if clear_pending_question:
            assessment.pending_question = None
            assessment.pending_options = None
        assessment.pending_followup_hint = pending_followup_hint
        assessment.pending_focus_capability_id = pending_focus_capability_id
        assessment.clarification_count = (
            int(assessment.clarification_count or 0) + 1
            if increment_clarification
            else 0
        )

        if increment_question_count:
            assessment.current_axis_question_count = int(assessment.current_axis_question_count or 0) + 1
        if increment_low_quality:
            assessment.current_axis_low_quality_count = int(assessment.current_axis_low_quality_count or 0) + 1
        if increment_question_count:
            await self.state.advance_if_axis_complete(
                assessment_id=assessment_id,
                assessment=assessment,
                max_extra_questions_per_axis=self._max_extra_questions_per_axis(),
            )

        self.state.bump_version(assessment)

    async def request_maturity_confirmation_followup(
        self,
        assessment_id: int,
        assessment: Any,
        answer: str,
        axis_capabilities: list[dict],
        focus_capability_id: int,
    ) -> AnswerResponse:
        await self.persist_answer(
            assessment_id=assessment_id,
            answer=answer,
            covered_ids=[],
            axis_capabilities=axis_capabilities,
            question_text=(assessment.pending_question or "").strip() or None,
            fallback_capability_id=focus_capability_id,
        )
        assessment.pending_question = None
        assessment.pending_options = None
        assessment.pending_followup_hint = self.question_flow.set_followup_hint(
            "maturity_confirmation",
            focus_capability_id,
        )
        assessment.pending_focus_capability_id = focus_capability_id
        assessment.clarification_count = int(assessment.clarification_count or 0) + 1
        assessment.current_axis_question_count = int(assessment.current_axis_question_count or 0) + 1
        self.state.bump_version(assessment)
        return AnswerResponse(
            status=assessment.status,
            axis=self.state.response_axis(assessment),
            covered=[],
            confidence=0.0,
        )


    async def persist_answer(
        self,
        assessment_id: int,
        answer: str,
        covered_ids: list[int],
        axis_capabilities: list[dict],
        question_text: str | None = None,
        fallback_capability_id: int | None = None,
    ) -> None:
        top_capability_id = covered_ids[0] if covered_ids else fallback_capability_id
        resolved_question = question_text
        if not resolved_question:
            resolved_question = "[system] question unavailable"
            if axis_capabilities:
                resolved_question = f"[system] {axis_capabilities[0]['label']}"
        await self.answers.create(
            assessment_id=assessment_id,
            question=resolved_question,
            answer=answer,
            capability_id=top_capability_id,
        )


def build_answer_flow_service(
    assessments: AssessmentRepository,
    capabilities: CapabilityRepository,
    answers: AssessmentAnswerRepository,
    llm_service: LLMService,
    state_service: AssessmentStateService,
    scoring_service: AssessmentScoringService,
    reporting_service: AssessmentReportingService,
    question_flow_service: QuestionFlowService,
    max_extra_questions_per_axis: Callable[[], int],
    max_clarifications_per_focus: Callable[[], int],
    max_insufficient_evidence_retries: Callable[[], int],
    schedule_axis_memory_update: Callable[[int, str, str, list[int], list[dict]], Awaitable[asyncio.Task[str] | None]],
    schedule_next_question_prefetch: Callable[
        [Any, int | None, str | None, asyncio.Task[str] | None],
        asyncio.Task[NextQuestionResponse | None] | None,
    ],
    cancel_scheduled_axis_memory_update: Callable[[asyncio.Task[str] | None], Awaitable[None]],
    cancel_scheduled_next_question_prefetch: Callable[[asyncio.Task[NextQuestionResponse | None] | None], Awaitable[None]],
    finalize_parallel_llm_tasks: Callable[[int, str, asyncio.Task[str] | None, asyncio.Task[NextQuestionResponse | None] | None], Awaitable[None]],
) -> AnswerFlowService:
    return AnswerFlowService(
        assessments=assessments,
        capabilities=capabilities,
        answers=answers,
        llm_service=llm_service,
        state_service=state_service,
        scoring_service=scoring_service,
        reporting_service=reporting_service,
        question_flow_service=question_flow_service,
        max_extra_questions_per_axis=max_extra_questions_per_axis,
        max_clarifications_per_focus=max_clarifications_per_focus,
        max_insufficient_evidence_retries=max_insufficient_evidence_retries,
        schedule_axis_memory_update=schedule_axis_memory_update,
        schedule_next_question_prefetch=schedule_next_question_prefetch,
        cancel_scheduled_axis_memory_update=cancel_scheduled_axis_memory_update,
        cancel_scheduled_next_question_prefetch=cancel_scheduled_next_question_prefetch,
        finalize_parallel_llm_tasks=finalize_parallel_llm_tasks,
    )
