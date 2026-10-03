from django.utils import timezone
from rest_framework import permissions, viewsets

from apps.accounts.models import User
from apps.core.permissions import IsOwnClubLeader

from .models import Activity
from .serializers import ActivitySerializer

class ActivityViewSet(viewsets.ModelViewSet):
    serializer_class = ActivitySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in (User.Role.COMMITTEE_HEAD, User.Role.STAFF, User.Role.SYSTEM_ADMIN):
            return Activity.objects.all()
        return Activity.objects.filter(club__memberships__user=user, club__memberships__role="leader") | \
               Activity.objects.filter(status="verified")  # verified activities are publicly viewable

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [permissions.IsAuthenticated(), IsOwnClubLeader()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(submitted_by=self.request.user, submitted_at=timezone.now())
