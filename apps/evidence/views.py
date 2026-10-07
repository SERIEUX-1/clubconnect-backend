from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import User
from apps.core.permissions import IsCommitteeMember, IsOwnClubLeader
from apps.core.tenancy import scope_club_owned

from .models import Evidence
from .serializers import EvidenceReviewSerializer, EvidenceSerializer

class EvidenceViewSet(viewsets.ModelViewSet):
    serializer_class = EvidenceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Evidence.objects.select_related("club", "activity")
        if user.role in (User.Role.COMMITTEE_HEAD, User.Role.STAFF, User.Role.STUDENT_LIFE, User.Role.SYSTEM_ADMIN):
            return scope_club_owned(qs, user)
        return qs.filter(club__memberships__user=user, club__memberships__role="leader")

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
