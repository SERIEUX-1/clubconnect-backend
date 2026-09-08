from django.utils import timezone
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.clubs.models import Club
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


class AICoachFeedbackView(APIView):
    """Provides practical, actionable club coaching guidance based on actual metrics."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        club_id = request.query_params.get("club")
        user = request.user
        club = None
        if club_id:
            club = Club.objects.filter(id=club_id).first()
        elif user.role == User.Role.CLUB_LEADER:
            membership = user.memberships.filter(role="leader").first()
            if membership:
                club = membership.club
        if not club:
            club = Club.objects.first()

        provider = get_provider()
        club_context = {
            "name": club.name if club else "Your Club",
            "activity_count": club.activities.count() if club else 0,
            "has_collaboration": club.incoming_collaborations.filter(status="confirmed").exists() if club else False,
        }
        feedback = provider.generate_coach_feedback(club_context)
        return Response({
            "club_id": str(club.id) if club else None,
            "club_name": club.name if club else None,
            "feedback": feedback,
            "generated_at": timezone.now().isoformat(),
        })
