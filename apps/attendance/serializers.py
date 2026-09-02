from rest_framework import serializers

from .models import AttendanceRecord


class AttendanceRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceRecord
        fields = ["id", "event", "user", "checked_in_at", "is_manual_correction", "correction_reason"]
        read_only_fields = ["id", "checked_in_at"]
