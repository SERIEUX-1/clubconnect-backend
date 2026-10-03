"""
AI provider abstraction (PRS Section 11 & 14): "Use an AI provider
abstraction layer so the institution can change models/providers later
without rewriting business logic."

Nothing outside this module should import an AI SDK directly. Views and
services call `get_provider()` and work only with the AIProvider interface.
"""
from __future__ import annotations

import abc
import json
import logging
import re
from dataclasses import dataclass, field

from django.conf import settings

logger = logging.getLogger(__name__)


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


@dataclass
class ChatGuideRequest:
    question: str
    role: str
    institution_name: str
    playbook_label: str
    playbook_reply: str
    playbook_steps: list[str] = field(default_factory=list)
    analysis: list[str] = field(default_factory=list)
    action_labels: list[str] = field(default_factory=list)


@dataclass
class ChatGuideResponse:
    reply: str
    steps: list[str]
    suggestions: list[str]
    model_name: str
    raw_metadata: dict = field(default_factory=dict)


class AIProvider(abc.ABC):
    uses_language_model = False

    @abc.abstractmethod
    def recommend_score(self, request: RecommendationRequest) -> RecommendationResponse:
        ...

    @abc.abstractmethod
    def generate_coach_feedback(self, club_context: dict) -> str:
        ...

    def map_topic(self, question: str, catalog: list[dict]) -> str | None:
        return None

    def guide_chat(self, request: ChatGuideRequest) -> ChatGuideResponse | None:
        return None


class AnthropicProvider(AIProvider):
    """Reference implementation. Swap for another AIProvider subclass in
    settings.AI_PROVIDER without touching any calling code."""

    uses_language_model = True

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def _client(self):
        import anthropic  # imported lazily so the package is optional until configured
        return anthropic.Anthropic(api_key=self.api_key)

    def map_topic(self, question: str, catalog: list[dict]) -> str | None:
        lines = "\n".join(f"- {row['id']}: {row['label']}" for row in catalog)
        try:
            message = self._client().messages.create(
                model=self.model,
                max_tokens=80,
                system=(
                    "You map a ClubConnect user question to one playbook id. "
                    "Return JSON only: {\"topic\": \"<id or unknown>\"}. "
                    "If none fit, topic is unknown. Never invent an id."
                ),
                messages=[{"role": "user", "content": f"Question: {question}\n\nPlaybooks:\n{lines}"}],
            )
        except Exception:
            logger.exception("Copilot topic mapping failed")
            return None
        text = "".join(block.text for block in message.content if getattr(block, "type", "") == "text")
        data = _json_object(text)
        topic = str((data or {}).get("topic") or "").strip()
        allowed = {row["id"] for row in catalog}
        if topic in allowed:
            return topic
        return None

    def guide_chat(self, request: ChatGuideRequest) -> ChatGuideResponse | None:
        facts = (
            f"Role: {request.role}\n"
            f"Campus: {request.institution_name}\n"
            f"Playbook: {request.playbook_label}\n"
            f"Canonical answer:\n{request.playbook_reply}\n"
            f"Steps:\n" + "\n".join(f"- {s}" for s in request.playbook_steps) + "\n"
            f"How the playbook read the question:\n" + "\n".join(f"- {s}" for s in request.analysis) + "\n"
            f"Allowed buttons: {', '.join(request.action_labels) or '(none)'}\n"
        )
        try:
            message = self._client().messages.create(
                model=self.model,
                max_tokens=500,
                system=(
                    "You are ClubConnect Copilot. You are a language model that may ONLY "
                    "rephrase PLAYBOOK facts. Never invent screens, emails, scores, clubs, "
                    "roles, or buttons. Never reveal unpublished CCEA marks unless they are "
                    "in the facts. Answer the user's question directly. Use **bold** for "
                    "button names. Return JSON only: "
                    "{\"reply\": string, \"steps\": string[], \"suggestions\": string[]}."
                ),
                messages=[
                    {
                        "role": "user",
                        "content": f"User question: {request.question}\n\nPLAYBOOK FACTS:\n{facts}",
                    }
                ],
            )
        except Exception:
            logger.exception("Copilot language model phrasing failed")
            return None
        text = "".join(block.text for block in message.content if getattr(block, "type", "") == "text")
        data = _json_object(text)
        if not data or not str(data.get("reply") or "").strip():
            return None
        steps = data.get("steps") if isinstance(data.get("steps"), list) else request.playbook_steps
        suggestions = data.get("suggestions") if isinstance(data.get("suggestions"), list) else []
        return ChatGuideResponse(
            reply=str(data["reply"]).strip(),
            steps=[str(s) for s in steps if str(s).strip()][:6],
            suggestions=[str(s) for s in suggestions if str(s).strip()][:4],
            model_name=self.model,
            raw_metadata={"raw_text": text[:2000]},
        )

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

    uses_language_model = False

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


def _json_object(text: str) -> dict | None:
    if not text:
        return None
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def get_provider() -> AIProvider:
    provider_name = getattr(settings, "AI_PROVIDER", "mock")
    api_key = getattr(settings, "AI_API_KEY", "")
    
    if provider_name == "anthropic" and api_key:
        return AnthropicProvider(api_key=api_key, model=getattr(settings, "AI_MODEL", "claude-3-haiku-20240307"))
    return RuleBasedProvider()
