from django.conf import settings
from django.db import models

from apps.core.models import BaseModel
from apps.evaluation.models import Score


class AIRecommendation(BaseModel):
    """
    PRS Section 11: AI recommends, humans decide. This table is the audit
    trail proving that rule was followed — it stores the recommendation,
    the explanation, and which model/version produced it, but a
    AIRecommendation NEVER writes directly to Score.final_value. Only
    apps.evaluation.services.apply_human_adjustment (called from a
    reviewer's authenticated action) may set final_value.
    """

    score = models.ForeignKey(Score, on_delete=models.CASCADE, related_name="ai_recommendations")
    recommended_value = models.DecimalField(max_digits=6, decimal_places=2)
    explanation = models.TextField()
    evidence_summary = models.TextField(blank=True)
    flags = models.JSONField(default=list, blank=True)  # e.g. ["missing_evidence", "possible_duplicate"]

    provider = models.CharField(max_length=50)
    model_name = models.CharField(max_length=100)
    model_version_metadata = models.JSONField(default=dict, blank=True)

    accepted_as_is = models.BooleanField(null=True, blank=True)  # set once a human reviews it

    class Meta:
        ordering = ["-created_at"]
