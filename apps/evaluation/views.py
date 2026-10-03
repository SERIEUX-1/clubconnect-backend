from decimal import Decimal, InvalidOperation

from django.utils import timezone
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.clubs.models import Club
from apps.core.permissions import IsCommitteeHead, IsCommitteeMember, IsStaffOrAdmin
from apps.core.tenancy import is_platform_operator

from .models import Appeal, EvaluationCriterion, EvaluationCycle, Score
from .brief import institutional_brief
from .monthly import campus_analytics, evaluate_club_month, evaluate_institution_month
from .serializers import (
    AppealSerializer, EvaluationCriterionSerializer, EvaluationCycleSerializer,
    ScoreAdjustmentSerializer, ScoreSerializer,
)
from .services import WeightConfigurationError, apply_human_adjustment, compute_month_score, validate_cycle_weights


class EvaluationCycleViewSet(viewsets.ModelViewSet):
    queryset = EvaluationCycle.objects.all()
    serializer_class = EvaluationCycleSerializer

    def get_permissions(self):
        return [permissions.IsAuthenticated(), IsCommitteeHead()]

    @action(detail=True, methods=["post"])
    def finalize(self, request, pk=None):
        """Locks a cycle after validating its criteria weights sum to
        100% — refuses to finalize a mis-configured framework rather than
        silently producing wrong scores (PRS Section 9)."""
        cycle = self.get_object()
        try:
            validate_cycle_weights(cycle)
        except WeightConfigurationError as exc:
            return Response({"error": str(exc)}, status=400)
        cycle.is_finalized = True
        cycle.finalized_by = request.user
        cycle.save(update_fields=["is_finalized", "finalized_by", "updated_at"])
        return Response(EvaluationCycleSerializer(cycle).data)


class EvaluationCriterionViewSet(viewsets.ModelViewSet):
    queryset = EvaluationCriterion.objects.all()
    serializer_class = EvaluationCriterionSerializer
    permission_classes = [permissions.IsAuthenticated, IsCommitteeHead]


class ScoreViewSet(viewsets.ModelViewSet):
    serializer_class = ScoreSerializer
    permission_classes = [permissions.IsAuthenticated, IsCommitteeHead]

    def get_queryset(self):
        user = self.request.user
        qs = Score.objects.select_related("criterion", "club")
        if user.institution_id and not is_platform_operator(user):
            return qs.filter(club__institution_id=user.institution_id)
        return qs

    @action(detail=True, methods=["get"])
    def month_breakdown(self, request, pk=None):
        score = self.get_object()
        result = compute_month_score(score.club, score.cycle, score.period_year, score.period_month)
        return Response({
            "total_score": str(result.total_score),
            "breakdown": [
                {"key": c.key, "label": c.label, "weight_percent": str(c.weight_percent),
                 "raw_value": str(c.raw_value), "weighted_contribution": str(c.weighted_contribution)}
                for c in result.breakdown
            ],
        })

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsCommitteeMember])
    def approve(self, request, pk=None):
        """The ONLY endpoint that can set a score's final, authoritative
        value. Requires an authenticated Committee reviewer and a reason —
        both enforced here, not trusted from the client."""
        score = self.get_object()
        try:
            new_value = Decimal(str(request.data.get("value")))
        except (InvalidOperation, TypeError):
            return Response({"error": "A numeric 'value' is required."}, status=400)
        reason = request.data.get("reason", "").strip()
        if not reason:
            return Response({"error": "A 'reason' is required for every score decision."}, status=400)

        adjustment = apply_human_adjustment(score, new_value, reason, request.user)
        return Response(ScoreAdjustmentSerializer(adjustment).data, status=201)


class AppealViewSet(viewsets.ModelViewSet):
    serializer_class = AppealSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in (User.Role.COMMITTEE_HEAD, User.Role.STAFF, User.Role.SYSTEM_ADMIN):
            return Appeal.objects.all()
        return Appeal.objects.filter(raised_by=user)

    def perform_create(self, serializer):
        serializer.save(raised_by=self.request.user)


class MonthlyEvaluationView(APIView):
    """
    GET /api/monthly-evaluations/?year=2026&month=9&club=<uuid>
    Rule-based monthly lackings for the caller's institution.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        now = timezone.now()
        year = int(request.query_params.get("year") or now.year)
        month = int(request.query_params.get("month") or now.month)
        user = request.user
        club_id = request.query_params.get("club")

        if club_id:
            club = Club.objects.filter(id=club_id).first()
            if not club:
                return Response({"error": "Club not found."}, status=404)
            if not is_platform_operator(user) and club.institution_id != user.institution_id:
                return Response({"error": "This club is not in your institution."}, status=403)
            if user.role == User.Role.COMMITTEE_HEAD:
                return Response(evaluate_club_month(club, year, month))
            if user.role == User.Role.CLUB_LEADER and user.is_leader_of(club):
                payload = evaluate_club_month(club, year, month)
                payload.pop("score", None)
                payload.pop("band", None)
                return Response(payload)
            return Response(
                {"error": "Campus Clubs Excellence Awards marks are only visible to the Committee Head until they are published."},
                status=403,
            )

        if user.role == User.Role.CLUB_LEADER:
            membership = user.club_memberships.filter(
                role="leader", status="approved"
            ).select_related("club").first()
            if not membership:
                return Response({"error": "No club leadership assignment found."}, status=404)
            payload = evaluate_club_month(membership.club, year, month)
            payload.pop("score", None)
            payload.pop("band", None)
            return Response(payload)
        if user.role != User.Role.COMMITTEE_HEAD:
            return Response(
                {"error": "Campus Clubs Excellence Awards marks and rankings are only visible to the Committee Head until they are published."},
                status=403,
            )

        if not user.institution_id and not is_platform_operator(user):
            return Response({"error": "No institution is attached to this account."}, status=400)
        payload = evaluate_institution_month(user.institution, year, month)
        return Response(payload)


class CampusAnalyticsView(APIView):
    """GET /api/campus-analytics/ — staff/lecturer campus snapshot."""

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        user = request.user
        if not user.institution_id and not is_platform_operator(user):
            return Response({"error": "No institution is attached to this account."}, status=400)
        return Response(campus_analytics(user.institution))


class CampusBriefView(APIView):
    """GET /api/campus-brief/ — live staff brief. Unpublished awards stay out."""

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        user = request.user
        if not user.institution_id and not is_platform_operator(user):
            return Response({"error": "No institution is attached to this account."}, status=400)
        return Response(institutional_brief(user.institution))
