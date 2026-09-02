from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import User
from apps.core.permissions import IsCommitteeMember, IsOwnClubLeader

from .models import Evidence
from .serializers import EvidenceReviewSerializer, EvidenceSerializer

class EvidenceViewSet(viewsets.ModelViewSet):
    serializer_class = EvidenceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in (User.Role.COMMITTEE_HEAD, User.Role.DEAN_ADMIN):
            return Evidence.objects.all()
        if user.role == User.Role.COMMITTEE_MEMBER:
            return Evidence.objects.filter(club_id__in=user.assigned_club_ids())
        return Evidence.objects.filter(club__memberships__user=user, club__memberships__role="leader")

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [permissions.IsAuthenticated(), IsOwnClubLeader()]
        if self.action == "review":
            return [permissions.IsAuthenticated(), IsCommitteeMember()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)

    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        """Creates an EvidenceReview record (preserving full history, PRS
        Section 7) and updates the evidence's current status. Never
        overwrites prior reviews."""
        evidence = self.get_object()
        status_value = request.data.get("status")
        comment = request.data.get("comment", "")
        if status_value not in dict(Evidence.Status.choices):
            return Response({"error": "Invalid status."}, status=400)
        review = evidence.reviews.create(reviewer=request.user, status=status_value, comment=comment)
        evidence.status = status_value
        evidence.save(update_fields=["status", "updated_at"])
        return Response(EvidenceReviewSerializer(review).data, status=201)
