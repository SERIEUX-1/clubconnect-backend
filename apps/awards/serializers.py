from rest_framework import serializers
from .models import Award, HallOfExcellenceEntry


def ceremony_year(value) -> str:
    """Hall of Excellence shows one calendar year, never a 2024-2025 range."""
    text = str(value or "").strip()
    if "-" in text:
        left, right = text.split("-", 1)
        for part in (left, right):
            digits = "".join(ch for ch in part if ch.isdigit())
            if len(digits) >= 4:
                return digits[:4]
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits[:4] if len(digits) >= 4 else text


class AwardSerializer(serializers.ModelSerializer):
    category = serializers.CharField(source="category_name", read_only=True)
    winner = serializers.SerializerMethodField()
    citation = serializers.CharField(source="description", read_only=True)

    class Meta:
        model = Award
        fields = [
            "id",
            "cycle",
            "category_name",
            "category",
            "description",
            "winner_club",
            "winner",
            "is_revealed",
            "revealed_at",
            "citation",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "category", "winner", "citation"]

    def get_winner(self, obj):
        if obj.winner_club_id:
            return obj.winner_club.name
        return ""


class HallOfExcellenceEntrySerializer(serializers.ModelSerializer):
    club_name = serializers.CharField(source="club.name", read_only=True)
    award = serializers.CharField(source="award.category_name", read_only=True)
    award_description = serializers.CharField(source="award.description", read_only=True)
    year = serializers.SerializerMethodField()

    class Meta:
        model = HallOfExcellenceEntry
        fields = [
            "id",
            "club",
            "club_name",
            "award",
            "award_description",
            "academic_year",
            "year",
            "citation",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "club_name",
            "year",
            "award",
            "award_description",
        ]

    def get_year(self, obj):
        return ceremony_year(obj.academic_year)
