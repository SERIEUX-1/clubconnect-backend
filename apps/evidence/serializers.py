from rest_framework import serializers
from .models import Evidence, EvidenceReview


class EvidenceSerializer(serializers.ModelSerializer):
    club_name = serializers.CharField(source="club.name", read_only=True)
    activity_title = serializers.SerializerMethodField()
    file_name = serializers.SerializerMethodField()
    reviewer_name = serializers.SerializerMethodField()
    reviewer_comment = serializers.SerializerMethodField()
    description = serializers.CharField(source="caption", read_only=True)

    class Meta:
        model = Evidence
        fields = [
            "id",
            "club",
            "club_name",
            "activity",
            "impact_project",
            "activity_title",
            "evidence_type",
            "file",
            "file_name",
            "external_link",
            "caption",
            "description",
            "status",
            "uploaded_by",
            "reviewer_name",
            "reviewer_comment",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "uploaded_by",
            "created_at",
            "updated_at",
            "club_name",
            "activity_title",
            "file_name",
            "reviewer_name",
            "reviewer_comment",
            "description",
        ]

    def get_activity_title(self, obj):
        return obj.activity.title if obj.activity_id else "General evidence"

    def get_file_name(self, obj):
        if obj.file:
            return obj.file.name.rsplit("/", 1)[-1]
        return ""

    def get_reviewer_name(self, obj):
        review = obj.reviews.select_related("reviewer").first()
        if review and review.reviewer:
            return review.reviewer.get_full_name() or review.reviewer.username
        return ""

    def get_reviewer_comment(self, obj):
        review = obj.reviews.first()
        return review.comment if review else ""


class EvidenceReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = EvidenceReview
        fields = "__all__"
        read_only_fields = ["id", "reviewer", "created_at", "updated_at"]
