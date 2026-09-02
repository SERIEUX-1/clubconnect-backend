from rest_framework import serializers
from .models import Collaboration

class CollaborationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Collaboration
        fields = "__all__"
        read_only_fields = ["id", "status", "confirmed_by", "confirmed_at", "created_at", "updated_at"]
