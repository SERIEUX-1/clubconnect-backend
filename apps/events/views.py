from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import IsOwnClubLeader

from .models import Event
from .serializers import EventQRSerializer, EventSerializer

class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy", "reveal_qr", "regenerate_qr"):
            return [permissions.IsAuthenticated(), IsOwnClubLeader()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["get"])
    def reveal_qr(self, request, pk=None):
        event = self.get_object()
        self.check_object_permissions(request, event)
        return Response(EventQRSerializer(event).data)

    @action(detail=True, methods=["post"])
    def regenerate_qr(self, request, pk=None):
        event = self.get_object()
        self.check_object_permissions(request, event)
        event.regenerate_qr_token()
        return Response(EventQRSerializer(event).data)
