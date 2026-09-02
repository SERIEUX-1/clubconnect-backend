from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.clubs.models import Club
from apps.core.models import BaseModel


class EvaluationCycle(BaseModel):
    """A configurable evaluation period (PRS Section 10). CCEA Cycle 1/2
    are just *data* created through this model — never special-cased in
    code by month name."""

    name = models.CharField(max_length=100)  # e.g. "CCEA Cycle 1 2026/27"
    evaluation_months = models.JSONField(help_text='List of "YYYY-MM" strings covered by this cycle')
    reveal_date = models.DateField()
    submission_deadline_day_of_month = models.PositiveSmallIntegerField(default=5)

    AGGREGATION_CHOICES = [
        ("weighted_average", "Weighted average by month"),
        ("simple_average", "Simple average"),
        ("custom", "Custom rule (see aggregation_config)"),
    ]
    aggregation_method = models.CharField(max_length=30, choices=AGGREGATION_CHOICES, default="simple_average")
    aggregation_config = models.JSONField(default=dict, blank=True)

    is_active = models.BooleanField(default=True)
    is_finalized = models.BooleanField(default=False)
    finalized_at = models.DateTimeField(null=True, blank=True)
    finalized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="finalized_cycles"
    )

    class Meta:
        ordering = ["-reveal_date"]


class EvaluationCriterion(BaseModel):
    """
    Versioned scoring criteria (PRS Section 9 & 18). Weights live in the
    database, editable by a Committee Head, never as Python constants —
    this is what lets a future committee change the framework without a
    code deployment.
    """

    cycle = models.ForeignKey(EvaluationCycle, on_delete=models.CASCADE, related_name="criteria")
    key = models.SlugField(max_length=60)  # e.g. "activity_consistency"
    label = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    weight_percent = models.DecimalField(
        max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    version = models.PositiveIntegerField(default=1)
    effective_date = models.DateField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["cycle", "key", "version"], name="unique_criterion_version")
        ]
        ordering = ["cycle", "key", "-version"]

    def __str__(self):
        return f"{self.label} ({self.weight_percent}%) v{self.version}"


class Score(BaseModel):
    """A single criterion/month score for a club. Final = human-approved."""

    class Stage(models.TextChoices):
        AI_RECOMMENDED = "ai_recommended", "AI Recommended"
        UNDER_REVIEW = "under_review", "Under Human Review"
        FINAL = "final", "Final (Authorized)"

    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="scores")
    cycle = models.ForeignKey(EvaluationCycle, on_delete=models.CASCADE, related_name="scores")
    criterion = models.ForeignKey(EvaluationCriterion, on_delete=models.PROTECT, related_name="scores")
    period_year = models.PositiveIntegerField()
    period_month = models.PositiveSmallIntegerField()

    ai_recommended_value = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    final_value = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    stage = models.CharField(max_length=20, choices=Stage.choices, default=Stage.AI_RECOMMENDED)

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_scores"
    )
    reviewer_notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["club", "cycle", "criterion", "period_year", "period_month"],
                name="unique_score_per_criterion_period",
            )
        ]


class ScoreAdjustment(BaseModel):
    """
    Immutable log entry: whenever a human overrides the AI recommendation,
    BOTH values and the reason are kept — never just overwritten (PRS
    Section 11: "If a reviewer changes the AI recommendation, store both
    values and the reason for the change.").
    """

    score = models.ForeignKey(Score, on_delete=models.CASCADE, related_name="adjustments")
    previous_value = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    new_value = models.DecimalField(max_digits=6, decimal_places=2)
    reason = models.TextField()
    adjusted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ["-created_at"]


class Appeal(BaseModel):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        UNDER_REVIEW = "under_review", "Under Review"
        UPHELD = "upheld", "Upheld (score changed)"
        DENIED = "denied", "Denied"

    score = models.ForeignKey(Score, on_delete=models.CASCADE, related_name="appeals")
    raised_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    resolution_notes = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="resolved_appeals"
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
