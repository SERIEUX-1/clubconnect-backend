from django.conf import settings
from django.db import models

from apps.core.models import BaseModel
from apps.events.models import Event


class AttendanceRecord(BaseModel):
    """PRS Section 8 requirements encoded directly in the schema:
    - Duplicate prevention -> unique_together constraint (not just app logic)
    - Auditability -> timestamp + correction fields kept, never overwritten
    - Privacy -> individual records restricted; aggregates computed on read
    """

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="attendance_records")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attendance_records")
    checked_in_at = models.DateTimeField(auto_now_add=True)

    is_manual_correction = models.BooleanField(default=False)
    corrected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="attendance_corrections",
    )
    correction_reason = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["event", "user"], name="unique_event_attendance")
        ]
        ordering = ["-checked_in_at"]
