from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class Notification(BaseModel):
    """PRS Section 5: deadlines, verification, collaboration and feedback
    notifications. Delivery is pluggable (PRS Section 18: 'Pluggable
    notification providers') — this model only stores the notification;
    apps/notifications/dispatch.py would hold the provider abstraction
    (email/push/in-app) following the same pattern as ai_assistant/providers.py."""

    class Category(models.TextChoices):
        DEADLINE = "deadline", "Deadline"
        VERIFICATION = "verification", "Verification"
        COLLABORATION = "collaboration", "Collaboration"
        FEEDBACK = "feedback", "Feedback"
        HEALTH_ALERT = "health_alert", "Club Health Alert"
        SYSTEM = "system", "System"

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    category = models.CharField(max_length=20, choices=Category.choices)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    link_url = models.CharField(max_length=300, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
