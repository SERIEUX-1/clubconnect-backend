from rest_framework import serializers
from .models import AIRecommendation

class AIRecommendationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIRecommendation
        fields = "__all__"
        read_only_fields = fields  # AI recommendations are generated, never hand-edited
