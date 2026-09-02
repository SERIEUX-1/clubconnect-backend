from rest_framework import serializers
from .models import Event

class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        exclude = ["qr_token"]  # never serialize the raw token in list/detail responses
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]

class EventQRSerializer(serializers.ModelSerializer):
    """Separate serializer used ONLY by the owning leader's dedicated
    'reveal QR' action — keeps the token out of every other response."""
    class Meta:
        model = Event
        fields = ["id", "qr_token"]
