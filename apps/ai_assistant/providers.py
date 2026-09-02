"""
AI provider abstraction (PRS Section 11 & 14): "Use an AI provider
abstraction layer so the institution can change models/providers later
without rewriting business logic."

Nothing outside this module should import an AI SDK directly. Views and
services call `get_provider()` and work only with the AIProvider interface.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass

from django.conf import settings


@dataclass
class RecommendationRequest:
    criterion_label: str
    criterion_description: str
    evidence_summaries: list[str]
    club_context: dict  # non-sensitive context only — see redact_for_ai()


@dataclass
class RecommendationResponse:
    recommended_value: float
    explanation: str
    flags: list[str]
    model_name: str
    raw_metadata: dict


class AIProvider(abc.ABC):
    @abc.abstractmethod
    def recommend_score(self, request: RecommendationRequest) -> RecommendationResponse:
        ...

    @abc.abstractmethod
    def generate_coach_feedback(self, club_context: dict) -> str:
        ...


class AnthropicProvider(AIProvider):
    """Reference implementation. Swap for another AIProvider subclass in
    settings.AI_PROVIDER without touching any calling code."""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def _client(self):
        import anthropic  # imported lazily so the package is optional until configured
        return anthropic.Anthropic(api_key=self.api_key)

    def recommend_score(self, request: RecommendationRequest) -> RecommendationResponse:
        prompt = self._build_scoring_prompt(request)
        client = self._client()
        message = client.messages.create(
            model=self.model,
            max_tokens=800,
            system=(
                "You are an evaluation assistant for a student-club performance "
                "framework. You ONLY recommend — you never issue a final decision. "
                "Base your recommendation strictly on the evidence provided. Never "
                "invent facts. If evidence is insufficient, say so and score low "
                "or flag 'missing_evidence' rather than guessing generously."
            ),
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in message.content if block.type == "text")
        return self._parse_response(text)

    def generate_coach_feedback(self, club_context: dict) -> str:
        client = self._client()
        message = client.messages.create(
            model=self.model,
            max_tokens=400,
            system=(
                "You are a supportive club-development coach. Give concrete, "
                "actionable, encouraging guidance using only the data provided. "
                "Never invent achievements or numbers that weren't given to you."
            ),
            messages=[{"role": "user", "content": str(club_context)}],
        )
        return "".join(block.text for block in message.content if block.type == "text")

    @staticmethod
    def _build_scoring_prompt(request: RecommendationRequest) -> str:
        evidence_block = "\n".join(f"- {e}" for e in request.evidence_summaries) or "(no evidence submitted)"
        return (
            f"Criterion: {request.criterion_label}\n"
            f"Description: {request.criterion_description}\n"
            f"Evidence submitted:\n{evidence_block}\n\n"
            "Respond with: a recommended score out of 100, a short explanation, "
            "and any flags (e.g. missing_evidence, possible_duplicate, inconsistent)."
        )

    @staticmethod
    def _parse_response(text: str) -> RecommendationResponse:
        # A production build should request structured JSON output (see the
        # "structured outputs" pattern) instead of parsing free text.
        return RecommendationResponse(
            recommended_value=0.0,
            explanation=text,
            flags=[],
            model_name=settings.AI_MODEL,
            raw_metadata={"raw_text": text},
        )


def get_provider() -> AIProvider:
    if settings.AI_PROVIDER == "anthropic":
        return AnthropicProvider(api_key=settings.AI_API_KEY, model=settings.AI_MODEL)
    raise NotImplementedError(f"Unknown AI_PROVIDER '{settings.AI_PROVIDER}'")
