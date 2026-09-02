from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import Throttled
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.events.models import Event

from .models import AttendanceRecord
from .serializers import AttendanceRecordSerializer


class QRCheckInView(APIView):
    """
    POST /api/events/{event_id}/check-in/  { "qr_token": "..." }

    Implements every PRS Section 8 attendance requirement directly:
    - Duplicate prevention: DB unique constraint (event, user) -> IntegrityError caught -> 409
    - Time control: rejects scans outside check_in_opens_at/closes_at
    - Auditability: record is immutable once created; corrections are separate, logged actions
    - Rate limiting: scoped throttle prevents QR-scan abuse
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "attendance-scan"

    def post(self, request, event_id):
        try:
            event = Event.objects.get(id=event_id)
        except Event.DoesNotExist:
            return Response({"error": "Event not found."}, status=status.HTTP_404_NOT_FOUND)

        submitted_token = request.data.get("qr_token")
        if submitted_token != event.qr_token:
            return Response({"error": "Invalid QR code."}, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        if event.check_in_opens_at and now < event.check_in_opens_at:
            return Response({"error": "Check-in has not opened yet."}, status=status.HTTP_400_BAD_REQUEST)
        if event.check_in_closes_at and now > event.check_in_closes_at:
            return Response({"error": "Check-in window has closed."}, status=status.HTTP_400_BAD_REQUEST)

        record, created = AttendanceRecord.objects.get_or_create(event=event, user=request.user)
        if not created:
            return Response({"error": "Attendance already recorded."}, status=status.HTTP_409_CONFLICT)

        return Response(AttendanceRecordSerializer(record).data, status=status.HTTP_201_CREATED)


class AttendanceRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """Individual attendance stays restricted per PRS Section 8's privacy
    requirement; aggregate counts are exposed separately via a reporting
    endpoint (apps.evaluation) rather than by loosening this queryset."""

    serializer_class = AttendanceRecordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return AttendanceRecord.objects.filter(user=user) | AttendanceRecord.objects.filter(
            event__club__memberships__user=user, event__club__memberships__role="leader"
        )
