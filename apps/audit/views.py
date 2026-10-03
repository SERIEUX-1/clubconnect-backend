from rest_framework import permissions, viewsets

from apps.accounts.models import User
from apps.core.tenancy import is_platform_operator

from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role not in (User.Role.COMMITTEE_HEAD, User.Role.SYSTEM_ADMIN):
            return AuditLog.objects.none()
        qs = AuditLog.objects.select_related("actor")
        if is_platform_operator(user):
            return qs
        if user.institution_id:
            return qs.filter(actor__institution_id=user.institution_id)
        return qs.none()
