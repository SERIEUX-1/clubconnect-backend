from django.db import models

from apps.clubs.models import Club
from apps.core.models import BaseModel


class ImpactProject(BaseModel):
    """PRS: focus on meaningful outcomes, not event counts."""

    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="impact_projects")
    title = models.CharField(max_length=200)
    problem_statement = models.TextField()
    objective = models.TextField()
    activities_summary = models.TextField(blank=True)

    beneficiaries_description = models.TextField()
    estimated_beneficiaries_count = models.PositiveIntegerField(default=0)

    outcomes = models.TextField(blank=True)
    metrics = models.JSONField(default=dict, blank=True)  # e.g. {"trees_planted": 120}
    lessons_learned = models.TextField(blank=True)
    next_steps = models.TextField(blank=True)

    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
