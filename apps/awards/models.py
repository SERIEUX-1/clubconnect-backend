from django.conf import settings
from django.db import models

from apps.clubs.models import Club
from apps.core.models import BaseModel
from apps.evaluation.models import EvaluationCycle


class Award(BaseModel):
    """Award categories are fully configurable rows, never a hard-coded
    enum in Python — PRS Section 17: 'Awards must be configurable.
    Future committees may add, remove or rename categories.'"""

    cycle = models.ForeignKey(EvaluationCycle, on_delete=models.CASCADE, related_name="awards")
    category_name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    winner_club = models.ForeignKey(Club, on_delete=models.SET_NULL, null=True, blank=True, related_name="awards_won")
    is_revealed = models.BooleanField(default=False)
    revealed_at = models.DateTimeField(null=True, blank=True)
    finalized_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)


class HallOfExcellenceEntry(BaseModel):
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="hall_of_excellence_entries")
    award = models.ForeignKey(Award, on_delete=models.CASCADE, related_name="hall_of_excellence_entries")
    academic_year = models.CharField(max_length=9)
    citation = models.TextField(blank=True)

    class Meta:
        ordering = ["-academic_year"]
