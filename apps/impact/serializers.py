from rest_framework import serializers
from .models import ImpactProject

class ImpactProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImpactProject
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]
