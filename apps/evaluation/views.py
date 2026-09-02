from decimal import Decimal, InvalidOperation

from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import User
from apps.core.permissions import IsCommitteeHead, IsCommitteeMember

from .models import Appeal, EvaluationCriterion, EvaluationCycle, Score
from .serializers import (
    AppealSerializer, EvaluationCriterionSerializer, EvaluationCycleSerializer,
    ScoreAdjustmentSerializer, ScoreSerializer,
)
from .services import WeightConfigurationError, apply_human_adjustment, compute_month_score, validate_cycle_weights


class EvaluationCycleViewSet(viewsets.ModelViewSet):
    queryset = EvaluationCycle.objects.all()
    serializer_class = EvaluationCycleSerializer

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy", "finalize"):
            return [permissions.IsAuthenticated(), IsCommitteeHead()]
        return [permissions.IsAuthenticated()]

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
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Score.objects.select_related("criterion", "club")
        if user.role in (User.Role.COMMITTEE_HEAD, User.Role.DEAN_ADMIN):
            return qs
        if user.role == User.Role.COMMITTEE_MEMBER:
            return qs.filter(club_id__in=user.assigned_club_ids())
        # Club leaders only ever see their OWN club's scores — this is the
        # server-side enforcement of PRS Section 12's confidentiality matrix.
        return qs.filter(club__memberships__user=user, club__memberships__role="leader")

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
        if user.role in (User.Role.COMMITTEE_HEAD, User.Role.COMMITTEE_MEMBER, User.Role.DEAN_ADMIN):
            return Appeal.objects.all()
        return Appeal.objects.filter(raised_by=user)

    def perform_create(self, serializer):
        serializer.save(raised_by=self.request.user)
