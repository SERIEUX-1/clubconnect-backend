from rest_framework import serializers

from .models import Appeal, EvaluationCriterion, EvaluationCycle, Score, ScoreAdjustment


class EvaluationCriterionSerializer(serializers.ModelSerializer):
    class Meta:
        model = EvaluationCriterion
        fields = ["id", "cycle", "key", "label", "description", "weight_percent", "version", "effective_date"]
        read_only_fields = ["id"]


class EvaluationCycleSerializer(serializers.ModelSerializer):
    criteria = EvaluationCriterionSerializer(many=True, read_only=True)

    class Meta:
        model = EvaluationCycle
        fields = [
            "id", "name", "evaluation_months", "reveal_date", "submission_deadline_day_of_month",
            "aggregation_method", "aggregation_config", "is_active", "is_finalized", "criteria",
        ]
        read_only_fields = ["id", "is_finalized"]


class ScoreSerializer(serializers.ModelSerializer):
    """
    `final_value` is intentionally read-only here. It can ONLY be changed
    via the `approve` action below, which routes through
    apps.evaluation.services.apply_human_adjustment — guaranteeing an
    audit trail entry is written every single time (PRS Section 11).
    """

    class Meta:
        model = Score
        fields = [
            "id", "club", "cycle", "criterion", "period_year", "period_month",
            "ai_recommended_value", "final_value", "stage", "reviewed_by", "reviewer_notes",
        ]
        read_only_fields = ["id", "final_value", "stage", "reviewed_by"]


class ScoreAdjustmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScoreAdjustment
        fields = ["id", "score", "previous_value", "new_value", "reason", "adjusted_by", "created_at"]
        read_only_fields = fields


class AppealSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appeal
        fields = ["id", "score", "raised_by", "reason", "status", "resolution_notes", "resolved_by", "resolved_at"]
        read_only_fields = ["id", "status", "resolved_by", "resolved_at"]
