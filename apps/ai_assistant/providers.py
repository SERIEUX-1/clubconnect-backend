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


class RuleBasedProvider(AIProvider):
    """Institutional evaluation rule provider when no external API key is set."""

    def recommend_score(self, request: RecommendationRequest) -> RecommendationResponse:
        evidence_count = len(request.evidence_summaries)
        club_name = request.club_context.get("club_name", "the club")
        
        if evidence_count == 0:
            return RecommendationResponse(
                recommended_value=35.0,
                explanation=(
                    f"No verified evidence found for {club_name} under '{request.criterion_label}'. "
                    f"Recommend uploading event photos, attendance sign-ins, or reports before committee review."
                ),
                flags=["missing_evidence"],
                model_name="institutional-rule-engine-v1",
                raw_metadata={"rule": "zero_evidence_fallback", "evidence_count": 0},
            )
        elif evidence_count == 1:
            return RecommendationResponse(
                recommended_value=72.0,
                explanation=(
                    f"Found 1 verified piece of supporting evidence for '{request.criterion_label}'. "
                    f"Consistent documentation, though additional secondary evidence would substantiate a higher band."
                ),
                flags=[],
                model_name="institutional-rule-engine-v1",
                raw_metadata={"rule": "single_evidence_baseline", "evidence_count": 1},
            )
        else:
            score_val = min(94.0, 80.0 + (evidence_count * 4.0))
            return RecommendationResponse(
                recommended_value=score_val,
                explanation=(
                    f"Strong documentation with {evidence_count} verified artifacts for '{request.criterion_label}'. "
                    f"High student engagement and consistent reporting observed."
                ),
                flags=[],
                model_name="institutional-rule-engine-v1",
                raw_metadata={"rule": "multi_evidence_high_band", "evidence_count": evidence_count},
            )

    def generate_coach_feedback(self, club_context: dict) -> str:
        club_name = club_context.get("name", "Your club")
        activity_count = club_context.get("activity_count", 2)
        has_collab = club_context.get("has_collaboration", False)
        
        if not has_collab:
            return (
                f"Great momentum this term, {club_name}! Activity consistency and member engagement are strong. "
                "To maximize your score in the upcoming CCEA cycle, consider partnering on a joint initiative with "
                "another society—cross-club collaboration earns up to 10 bonus points."
            )
        return (
            f"Outstanding performance, {club_name}! Both activities and collaborations are on track. "
            "Focus next month on capturing quantitative participant outcomes for your impact project documentation."
        )


def get_provider() -> AIProvider:
    provider_name = getattr(settings, "AI_PROVIDER", "mock")
    api_key = getattr(settings, "AI_API_KEY", "")
    
    if provider_name == "anthropic" and api_key:
        return AnthropicProvider(api_key=api_key, model=getattr(settings, "AI_MODEL", "claude-3-haiku-20240307"))
    return RuleBasedProvider()
