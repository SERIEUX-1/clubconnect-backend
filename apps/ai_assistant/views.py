from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsCommitteeMember
from apps.evaluation.models import Score

from .models import AIRecommendation
from .providers import RecommendationRequest, get_provider
from .serializers import AIRecommendationSerializer


class AIRecommendationViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only: recommendations are created only by GenerateRecommendationView
    below, never via direct POST, so every one is traceable to a real
    provider call with model metadata attached."""

    serializer_class = AIRecommendationSerializer
    permission_classes = [permissions.IsAuthenticated, IsCommitteeMember]
    queryset = AIRecommendation.objects.all()


class GenerateRecommendationView(APIView):
    """
    POST /api/scores/{score_id}/generate-ai-recommendation/

    Human-governance workflow (PRS Section 11): this endpoint only ever
    WRITES an AIRecommendation + sets Score.ai_recommended_value /
    Score.stage=AI_RECOMMENDED. It never sets Score.final_value — only
    apps.evaluation.views.ScoreViewSet.approve (a Committee action with a
    required reason) can do that.
    """

    permission_classes = [permissions.IsAuthenticated, IsCommitteeMember]

    def post(self, request, score_id):
        score = Score.objects.select_related("criterion", "club").get(id=score_id)
        evidence_summaries = list(
            score.club.evidence_items.filter(activity__isnull=False, status="verified")
            .values_list("caption", flat=True)
        )
        provider = get_provider()
        result = provider.recommend_score(
            RecommendationRequest(
                criterion_label=score.criterion.label,
                criterion_description=score.criterion.description,
                evidence_summaries=evidence_summaries,
                club_context={"club_name": score.club.name},
            )
        )
        recommendation = AIRecommendation.objects.create(
            score=score,
            recommended_value=result.recommended_value,
            explanation=result.explanation,
            flags=result.flags,
            provider="anthropic",
            model_name=result.model_name,
            model_version_metadata=result.raw_metadata,
        )
        score.ai_recommended_value = result.recommended_value
        score.stage = Score.Stage.UNDER_REVIEW
        score.save(update_fields=["ai_recommended_value", "stage", "updated_at"])
        return Response(AIRecommendationSerializer(recommendation).data, status=201)
