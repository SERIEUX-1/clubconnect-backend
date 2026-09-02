from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class AuditLog(BaseModel):
    """
    PRS Section 4 & 12: 'important decisions must leave a trace of who
    changed what, when and why.' This table is append-only at the
    application level — nothing in this codebase updates or deletes an
    AuditLog row. Populated via apps/audit/signals.py listening to
    post_save/post_delete on sensitive models (scores, evidence reviews,
    role changes, admin actions).
    """

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="audit_actions")
    action = models.CharField(max_length=100)  # e.g. "score.adjusted", "role.changed"
    target_model = models.CharField(max_length=100)
    target_id = models.CharField(max_length=64)
    reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["target_model", "target_id"])]
