from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from django.utils import timezone

from apps.accounts.models import User
from apps.clubs.models import ClubMembership
from apps.core.permissions import IsCampusInsight
from apps.core.tenancy import is_platform_operator
from apps.evaluation.monthly import evaluate_institution_month

from .dispatch import notify
from .models import Notification
from .serializers import NotificationSerializer


class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)


class BroadcastNoticeView(APIView):
    """Staff/lecturers send a campus notice. Recipients get an in-app notification."""

    permission_classes = [permissions.IsAuthenticated, IsCampusInsight]

    def post(self, request):
        user = request.user
        if not user.institution_id and not is_platform_operator(user):
            return Response({"error": "No institution is attached to this account."}, status=400)

        subject = (request.data.get("subject") or "").strip()
        message = (request.data.get("message") or "").strip()
        audience = request.data.get("audience") or "all_clubs"
        priority = request.data.get("priority") or "normal"
        if not subject or not message:
            return Response({"error": "Subject and message are required."}, status=400)

        institution = user.institution
        members = User.objects.filter(institution=institution, is_active=True).exclude(id=user.id)

        if audience == "staff_advisors":
            members = members.filter(role=User.Role.STAFF)
        elif audience == "committee_head":
            members = members.filter(role=User.Role.COMMITTEE_HEAD)
        elif audience == "attention_clubs":
            now = timezone.now()
            evaluation = evaluate_institution_month(institution, now.year, now.month)
            flagged = {
                row["club_id"]
                for row in evaluation["at_risk"] + evaluation["needs_attention"]
            }
            leader_ids = ClubMembership.objects.filter(
                club_id__in=flagged,
                role=ClubMembership.MembershipRole.LEADER,
                status=ClubMembership.Status.APPROVED,
            ).values_list("user_id", flat=True)
            members = members.filter(id__in=leader_ids)

        category = (
            Notification.Category.HEALTH_ALERT
            if priority == "urgent"
            else Notification.Category.SYSTEM
        )
        prefix = "Urgent: " if priority == "urgent" else ""
        created = 0
        for recipient in members:
            notify(
                recipient=recipient,
                category=category,
                title=f"{prefix}{subject}",
                body=message,
                link_url="/student-dashboard",
            )
            created += 1

        return Response(
            {
                "sent": created,
                "audience": audience,
                "priority": priority,
                "subject": subject,
            },
            status=status.HTTP_201_CREATED,
        )
