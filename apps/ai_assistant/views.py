from django.utils import timezone
from rest_framework import permissions, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.clubs.models import Club
from apps.core.permissions import IsCommitteeHead, IsCommitteeMember
from apps.core.tenancy import is_platform_operator
from apps.evaluation.models import Score
from apps.evaluation.monthly import evaluate_club_month

from .copilot import answer as copilot_answer
from .copilot import coach_brief, committee_head_briefing, health_scan
from .models import AIRecommendation
from .serializers import AIRecommendationSerializer


class AIRecommendationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AIRecommendationSerializer
    permission_classes = [permissions.IsAuthenticated, IsCommitteeMember]
    queryset = AIRecommendation.objects.all()


class GenerateRecommendationView(APIView):
    """Copilot recommends; humans still finalise the score."""

    permission_classes = [permissions.IsAuthenticated, IsCommitteeMember]

    def post(self, request, score_id):
        score = Score.objects.select_related("criterion", "club").get(id=score_id)
        result = evaluate_club_month(score.club, score.period_year, score.period_month)
        flags = [item["code"] for item in result["lackings"]]
        explanation = (
            f"Copilot evaluated {result['club_name']} for {score.period_year}-{score.period_month:02d} "
            f"on reports, QR attendance, confirmed collaborations, and evidence. "
            f"Recommended {result['score']}/100 ({result['band']}). "
            + ("Lackings: " + "; ".join(item["title"] for item in result["lackings"]) + ". " if result["lackings"] else "No lackings. ")
            + "Pending collaborations are excluded. This is not a final CCEA score."
        )
        recommendation = AIRecommendation.objects.create(
            score=score,
            recommended_value=result["score"],
            explanation=explanation,
            flags=flags,
            provider="copilot",
            model_name="clubconnect-copilot-v1",
            model_version_metadata={"engine": result.get("engine"), "signals": result.get("signals")},
        )
        score.ai_recommended_value = result["score"]
        score.stage = Score.Stage.UNDER_REVIEW
        score.save(update_fields=["ai_recommended_value", "stage", "updated_at"])
        return Response(AIRecommendationSerializer(recommendation).data, status=201)


class CopilotBriefView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        club_id = request.query_params.get("club")
        club = None
        if club_id:
            club = Club.objects.filter(id=club_id).first()
            if club and not is_platform_operator(user) and user.institution_id and club.institution_id != user.institution_id:
                return Response({"error": "That club is not in your institution."}, status=403)
        elif user.role == User.Role.CLUB_LEADER:
            membership = user.club_memberships.filter(role="leader").first()
            if membership:
                club = membership.club
        payload = coach_brief(user, club=club)
        payload.setdefault("generated_at", timezone.now().isoformat())
        return Response(payload)


class CopilotHealthScanView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsCommitteeHead]

    def get(self, request):
        user = request.user
        if not user.institution_id and not is_platform_operator(user):
            return Response({"error": "No institution is attached to this account."}, status=400)
        now = timezone.now()
        year = int(request.query_params.get("year") or now.year)
        month = int(request.query_params.get("month") or now.month)
        return Response(health_scan(user.institution, year=year, month=month))


class CopilotCommitteeBriefingView(APIView):
    """Most-urgent-first summary for Clubs and Societies Committee Head."""

    permission_classes = [permissions.IsAuthenticated, IsCommitteeHead]

    def get(self, request):
        user = request.user
        if not user.institution_id and not is_platform_operator(user):
            return Response({"error": "No institution is attached to this account."}, status=400)
        now = timezone.now()
        year = int(request.query_params.get("year") or now.year)
        month = int(request.query_params.get("month") or now.month)
        since = request.query_params.get("since")
        return Response(
            committee_head_briefing(user.institution, year=year, month=month, user=user, since=since)
        )


class CopilotChatView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        user_message = request.data.get("message", "").strip()
        if not user_message:
            return Response({"error": "message is required"}, status=400)
        role = request.data.get("role")
        if request.user.is_authenticated:
            role = request.user.role
        role = role or "guest"
        context = request.data.get("context") or {}
        if request.user.is_authenticated and not context.get("user_name"):
            context["user_name"] = request.user.get_full_name() or request.user.username
        payload = copilot_answer(
            user_message,
            role,
            user=request.user if request.user.is_authenticated else None,
            context=context,
        )
        return Response(payload)


class AICoachFeedbackView(CopilotBriefView):
    """Backward-compatible /api/ai-coach/ → Copilot brief."""


class AIChatGuidanceView(CopilotChatView):
    """Alias so existing clients on /api/ai-assistant/chat/ keep working."""
