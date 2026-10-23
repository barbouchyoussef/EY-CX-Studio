"""Working out what a client's message IS, before working out what it says.

Four kinds arrive in a diagnostic chat: a real answer, a request to repeat or rephrase
(CONFUSION), a return to something earlier (RESUME), and a message too thin to score at all
(LOW_QUALITY). The conversation branches hard on this, so it is decided first and separately.

Most messages never reach the model. `fast_route` settles the obvious cases deterministically --
that is what makes the chat feel responsive, since a one-word reply does not deserve a round trip.
The model is the fallback for genuinely ambiguous text.

With no API key configured the router answers LOW_QUALITY, which asks the client to say more. That
is the safe direction to fail in: it never scores a capability on an answer nobody classified.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable

from app.core.config import Settings
from app.services.llm.prompts import INTENT_ROUTER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class IntentRouter:
    """Intent classification with deterministic fast-path and LLM fallback."""

    _INTENT_LABELS = {"CONFUSION", "RESUME", "VALID_ANSWER", "LOW_QUALITY"}

    def __init__(
        self,
        settings: Settings,
        chat_messages: Callable[[list[dict[str, str]]], Awaitable[str]],
        clean_text: Callable[[str | None], str],
    ) -> None:
        self.settings = settings
        self._chat_messages = chat_messages
        self._clean_text = clean_text

    async def route(self, text: str, previous_question: str | None = None) -> str:
        cleaned_text = self._clean_text(text)
        cleaned_previous_question = self._clean_text(previous_question or "")
        fast_intent = self.fast_route(cleaned_text, previous_question=cleaned_previous_question)
        if fast_intent is not None:
            return fast_intent

        if not self.settings.mistral_api_key:
            logger.error("Cannot route user intent because MISTRAL_API_KEY is not set.")
            return "LOW_QUALITY"

        messages = [
            {"role": "system", "content": INTENT_ROUTER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "<intent_context>\n"
                    f"<previous_assistant_question>{cleaned_previous_question or 'n/a'}</previous_assistant_question>\n"
                    f"<user_message>{cleaned_text}</user_message>\n"
                    "</intent_context>"
                ),
            },
        ]
        try:
            raw_intent = await self._chat_messages(messages)
        except Exception as exc:
            logger.error("LLM intent routing failed: %s", exc, exc_info=True)
            return "LOW_QUALITY"

        intent = self._clean_text(raw_intent).upper()
        if intent not in self._INTENT_LABELS:
            logger.error("LLM returned invalid intent label: %r", raw_intent)
            return "LOW_QUALITY"
        return intent

    def fast_route(self, text: str, previous_question: str | None = None) -> str | None:
        normalized = self.normalize_fast_intent_text(text)
        if self.is_placeholder_noise_text(normalized):
            return "LOW_QUALITY"
        if self.is_negative_evidence_text(normalized, previous_question=previous_question):
            return "VALID_ANSWER"
        if self.is_affirmative_evidence_text(normalized, previous_question=previous_question):
            return "VALID_ANSWER"
        if self.is_confusion_request_text(normalized):
            return "CONFUSION"
        if normalized in {
            "pass",
            "skip",
            "go on",
            "move on",
            "next",
            "continue",
            "suivant",
            "on continue",
            "continuer",
        }:
            return "RESUME"
        return None

    def is_placeholder_noise_text(self, normalized_text: str) -> bool:
        if not normalized_text:
            return True

        noise_patterns = (
            r"\b(bla\s*bla(?:\s*bla)*)\b",
            r"\b(blah\s*blah(?:\s*blah)*)\b",
            r"\b(lorem ipsum)\b",
        )
        if any(re.search(pattern, normalized_text) for pattern in noise_patterns):
            return True

        tokens = normalized_text.split()
        if normalized_text in {"test", "test test", "this is a test", "ceci est un test"}:
            return True
        if len(tokens) >= 3 and len(set(tokens)) == 1:
            return True
        if self._looks_like_keyboard_mash(tokens):
            return True
        return False

    def _looks_like_keyboard_mash(self, tokens: list[str]) -> bool:
        letter_only = [token for token in tokens if token.isalpha()]
        if not letter_only:
            return False

        suspicious_tokens: list[str] = []
        meaningful_tokens: list[str] = []
        for token in letter_only:
            if len(token) < 6:
                meaningful_tokens.append(token)
                continue
            unique_ratio = len(set(token)) / len(token)
            vowel_ratio = sum(1 for char in token if char in "aeiouy") / len(token)
            if unique_ratio >= 0.8 and vowel_ratio <= 0.2:
                suspicious_tokens.append(token)
            else:
                meaningful_tokens.append(token)

        if not suspicious_tokens:
            return False

        if len(letter_only) == 1 and len(suspicious_tokens) == 1:
            return True

        return len(suspicious_tokens) >= 2 and len(suspicious_tokens) >= len(meaningful_tokens)

    def normalize_fast_intent_text(self, text: str) -> str:
        value = self._clean_text(text).lower()
        value = re.sub(r"[^\w\s]", "", value)
        return re.sub(r"\s+", " ", value).strip()

    def is_negative_evidence_answer(self, text: str, previous_question: str | None = None) -> bool:
        return self.is_negative_evidence_text(
            self.normalize_fast_intent_text(text),
            previous_question=self.normalize_fast_intent_text(previous_question or "") if previous_question else None,
        )

    def is_affirmative_evidence_text(self, normalized_text: str, previous_question: str | None = None) -> bool:
        if normalized_text not in {"yes", "yeah", "yep", "sure", "oui", "exactement"}:
            return False
        return self._question_supports_brief_affirmative_evidence(previous_question or "")

    def _question_supports_brief_affirmative_evidence(self, normalized_question: str) -> bool:
        if not normalized_question:
            return False
        return bool(
            re.search(
                r"\b("
                r"do you|did you|have you|are you|is it|"
                r"does it|can you|could you|would you|"
                r"est ce que|avez vous|utilisez vous|suivez vous|mesurez vous|collectez vous|"
                r"pouvez vous|est il|est elle|"
                r"for example|par exemple"
                r")\b",
                normalized_question,
            )
        )

    def is_negative_evidence_text(self, normalized_text: str, previous_question: str | None = None) -> bool:
        if normalized_text in {
            "idk",
            "i dont know",
            "i do not know",
            "dont know",
            "do not know",
            "no idea",
            "not yet",
            "je ne sais pas",
            "j en sais rien",
            "pas encore",
        }:
            return True
        if normalized_text in {"none", "nothing", "no", "non", "aucun", "aucune", "rien"}:
            return self._question_supports_brief_negative_evidence(previous_question or "")
        return any(
            re.search(pattern, normalized_text)
            for pattern in (
                r"\b(i|we|they|team|teams)\s+"
                r"(dont|do not|doesnt|does not|didnt|did not)\s+"
                r"(know|have|use|track|measure|collect|manage)\b",
                r"\b(no|not)\s+(formal\s+)?(process|owner|tool|tracking|system|cadence|routine)\b",
                r"\b(no|none)\s+(that\s+)?(i|we|they)\s+(know|know of|can share)\b",
                r"\b(pas de|aucun|aucune|sans)\s+(processus|outil|suivi|responsable|routine)\b",
                r"\b(nous navons pas|on na pas|je nai pas|il ny a pas)\b",
            )
        )

    def _question_supports_brief_negative_evidence(self, normalized_question: str) -> bool:
        if not normalized_question:
            return False
        return bool(
            re.search(
                r"\b("
                r"do you have|did you have|have you|"
                r"do you use|did you use|"
                r"do you track|did you track|"
                r"do you measure|did you measure|"
                r"do you collect|did you collect|"
                r"is there|was there|are there|"
                r"any |any$|"
                r"what tool|which tool|what system|which system|"
                r"what process|which process|"
                r"what owner|which owner|who owns|who is responsible|"
                r"quel outil|quel systeme|quel processus|"
                r"est ce quil y a|avez vous|utilisez vous|suivez vous|mesurez vous|collectez vous|"
                r"y a t il|existe t il"
                r")\b",
                normalized_question,
            )
        )

    def is_confusion_request_text(self, normalized_text: str) -> bool:
        if normalized_text in {
            "example",
            "an example",
            "give example",
            "give me an example",
            "can you give an example",
            "can you give me an example",
            "could you give an example",
            "could you give me an example",
            "explain",
            "explain please",
            "please explain",
            "simplify",
            "simple terms",
            "in simple terms",
            "say it simply",
            "make it simple",
            "what do you mean",
            "what does that mean",
            "i dont understand",
            "i do not understand",
            "can you explain",
            "could you explain",
            "which steps",
            "what steps",
            "explique",
            "explique moi",
            "expliquez",
            "expliquez moi",
            "je ne comprends pas",
            "je comprends pas",
            "que voulez vous dire",
        }:
            return True
        return normalized_text.startswith(
            (
                "explain ",
                "please explain ",
                "can you explain ",
                "could you explain ",
                "simplify ",
                "in simple terms ",
                "what do you mean ",
                "what does that mean ",
                "give me an example ",
            )
        )


def build_intent_router(
    settings: Settings,
    chat_messages: Callable[[list[dict[str, str]]], Awaitable[str]],
    clean_text: Callable[[str | None], str],
) -> IntentRouter:
    return IntentRouter(
        settings=settings,
        chat_messages=chat_messages,
        clean_text=clean_text,
    )
