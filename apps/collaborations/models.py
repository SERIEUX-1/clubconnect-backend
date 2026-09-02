from django.conf import settings
from django.db import models

from apps.activities.models import Activity
from apps.clubs.models import Club
from apps.core.models import BaseModel


class Collaboration(BaseModel):
    """
    PRS Section 8, non-negotiable rule: "Never award collaboration points
    solely because one club typed another club's name." Scoring code
    (apps.evaluation) must only count collaborations where status ==
    CONFIRMED, never PENDING.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending Confirmation"
        CONFIRMED = "confirmed", "Confirmed"
        REJECTED = "rejected", "Rejected"

    initiating_club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="initiated_collaborations")
    partner_club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="received_collaborations")
    activity = models.ForeignKey(Activity, on_delete=models.SET_NULL, null=True, blank=True)

    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="confirmed_collaborations",
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=~models.Q(initiating_club=models.F("partner_club")),
                name="collaboration_distinct_clubs",
            )
        ]
