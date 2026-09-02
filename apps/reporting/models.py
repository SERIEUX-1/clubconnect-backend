from django.conf import settings
from django.db import models

from apps.clubs.models import Club
from apps.core.models import BaseModel


class MonthlyReport(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        LATE = "late", "Submitted Late"
        MISSING = "missing", "Missing"

    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="monthly_reports")
    # Period is a plain (year, month) pair, not tied to any hard-coded
    # cycle logic — PRS Section 10 requires evaluation periods to be fully
    # configurable, not hard-coded (e.g. "March logic").
    period_year = models.PositiveIntegerField()
    period_month = models.PositiveSmallIntegerField()

    summary = models.TextField(blank=True)
    highlights = models.TextField(blank=True)
    challenges = models.TextField(blank=True)

    status = models.CharField(max_length=15, choices=Status.choices, default=Status.DRAFT)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    deadline = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["club", "period_year", "period_month"], name="unique_monthly_report")
        ]
        ordering = ["-period_year", "-period_month"]
