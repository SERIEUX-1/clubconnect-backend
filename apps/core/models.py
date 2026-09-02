import uuid

from django.db import models


class BaseModel(models.Model):
    """
    Every domain entity inherits this. UUID primary keys avoid leaking
    sequential IDs (e.g. guessing club_id=14 -> club_id=15) and make the
    schema safe to merge across environments/campuses later (PRS Section 18:
    multi-campus support as a future capability).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class SoftDeleteModel(BaseModel):
    """
    Institutional memory must survive (PRS Section 2: Institutional
    continuity). Nothing club-related is ever hard-deleted; it's archived.
    """

    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True
