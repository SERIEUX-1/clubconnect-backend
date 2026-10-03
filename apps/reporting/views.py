from datetime import timedelta

from django.utils import timezone
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import User
from apps.core.tenancy import is_platform_operator, scope_club_owned

from .models import MonthlyReport
from .serializers import MonthlyReportSerializer


class MonthlyReportViewSet(viewsets.ModelViewSet):
    serializer_class = MonthlyReportSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = scope_club_owned(MonthlyReport.objects.all(), user)
        if user.role in (
            User.Role.COMMITTEE_HEAD,
            User.Role.STAFF,
            User.Role.SYSTEM_ADMIN,
        ) or is_platform_operator(user):
            return qs
        return qs.filter(club__memberships__user=user, club__memberships__role="leader")

    def perform_create(self, serializer):
        deadline = serializer.validated_data.get("deadline") or (timezone.now() + timedelta(days=7))
        serializer.save(submitted_by=self.request.user, deadline=deadline)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        report = self.get_object()
        report.status = MonthlyReport.Status.SUBMITTED
        if timezone.now() > report.deadline:
            report.status = MonthlyReport.Status.LATE
        report.submitted_by = request.user
        report.submitted_at = timezone.now()
        report.save(update_fields=["status", "submitted_by", "submitted_at", "updated_at"])
        return Response(MonthlyReportSerializer(report).data)
