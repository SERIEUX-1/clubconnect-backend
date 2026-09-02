from django.utils import timezone
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import IsOwnClubLeader

from .models import Collaboration
from .serializers import CollaborationSerializer

class CollaborationViewSet(viewsets.ModelViewSet):
    """The mutual-confirmation workflow from PRS Section 8: initiating club
    creates it (status=PENDING); ONLY the partner club's leader may confirm
    or reject. Scoring code must filter status=CONFIRMED — see
    apps.evaluation — never counting a one-sided claim."""

    serializer_class = CollaborationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Collaboration.objects.filter(initiating_club__memberships__user=user) | \
               Collaboration.objects.filter(partner_club__memberships__user=user)

    def perform_create(self, serializer):
        club = serializer.validated_data["initiating_club"]
        if not club.leaders.filter(id=self.request.user.id).exists():
            raise permissions.PermissionDenied("Only a leader of the initiating club may create this.")
        serializer.save()

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        collab = self.get_object()
        if not collab.partner_club.leaders.filter(id=request.user.id).exists():
            return Response({"error": "Only the partner club's leader may confirm."}, status=403)
        collab.status = Collaboration.Status.CONFIRMED
        collab.confirmed_by = request.user
        collab.confirmed_at = timezone.now()
        collab.save(update_fields=["status", "confirmed_by", "confirmed_at", "updated_at"])
        return Response(CollaborationSerializer(collab).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        collab = self.get_object()
        if not collab.partner_club.leaders.filter(id=request.user.id).exists():
            return Response({"error": "Only the partner club's leader may reject."}, status=403)
        collab.status = Collaboration.Status.REJECTED
        collab.save(update_fields=["status", "updated_at"])
        return Response(CollaborationSerializer(collab).data)
