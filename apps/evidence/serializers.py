from rest_framework import serializers
from .models import Evidence, EvidenceReview

class EvidenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Evidence
        fields = "__all__"
        read_only_fields = ["id", "status", "uploaded_by", "created_at", "updated_at"]

class EvidenceReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = EvidenceReview
        fields = "__all__"
        read_only_fields = ["id", "reviewer", "created_at", "updated_at"]
