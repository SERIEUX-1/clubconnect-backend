import secrets

from django.conf import settings
from django.db import models

from apps.activities.models import Activity
from apps.clubs.models import Club
from apps.core.models import BaseModel


class Event(BaseModel):
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="events")
    activity = models.ForeignKey(Activity, on_delete=models.SET_NULL, null=True, blank=True, related_name="events")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    location = models.CharField(max_length=200, blank=True)

    registration_required = models.BooleanField(default=False)
    capacity = models.PositiveIntegerField(null=True, blank=True)

    # Event-bound QR secret (PRS Section 8). Never expose the raw token in
    # list endpoints — only to the club leader who owns the event, rendered
    # as a QR image, and it is regenerable if compromised.
    qr_token = models.CharField(max_length=64, unique=True, editable=False)
    check_in_opens_at = models.DateTimeField(null=True, blank=True)
    check_in_closes_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    def save(self, *args, **kwargs):
        if not self.qr_token:
            self.qr_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def regenerate_qr_token(self):
        self.qr_token = secrets.token_urlsafe(32)
        self.save(update_fields=["qr_token", "updated_at"])

    class Meta:
        ordering = ["-starts_at"]
