from django.conf import settings
from django.db import models

from apps.clubs.models import Club
from apps.core.models import BaseModel


class Activity(BaseModel):
    """Structured activity record (PRS Section 7). Deliberately does NOT
    require a minimum number of files — evidence is validated for
    relevance, not volume, per the PRS design principle "evidence before
    claims", not evidence for its own sake."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Under Review"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"
        REVISION_REQUIRED = "revision_required", "Revision Required"

    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="activities")
    title = models.CharField(max_length=200)
    activity_type = models.CharField(max_length=100)
    date_time = models.DateTimeField()
    location = models.CharField(max_length=200, blank=True)

    objective = models.TextField()
    description = models.TextField(blank=True)
    expected_outcome = models.TextField(blank=True)

    expected_participation = models.PositiveIntegerField(default=0)
    actual_participation = models.PositiveIntegerField(null=True, blank=True)

    collaborating_clubs = models.ManyToManyField(Club, blank=True, related_name="collaborated_activities")
    beneficiaries_description = models.TextField(blank=True)
    impact_metrics = models.JSONField(default=dict, blank=True)

    report_text = models.TextField(blank=True)
    lessons_learned = models.TextField(blank=True)

    status = models.CharField(max_length=25, choices=Status.choices, default=Status.DRAFT)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="submitted_activities"
    )
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date_time"]
        indexes = [models.Index(fields=["club", "status"])]
