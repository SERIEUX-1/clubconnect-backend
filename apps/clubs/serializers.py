from rest_framework import serializers

from .models import Club, ClubBudgetSpend, ClubConceptNote, ClubMembership, LeadershipHandover, LeadershipTerm


class ClubPublicSerializer(serializers.ModelSerializer):
    institution_name = serializers.CharField(source="institution.short_name", read_only=True)
    institution_slug = serializers.SlugField(source="institution.slug", read_only=True)
    logo_initial = serializers.SerializerMethodField()
    published_watch_count = serializers.SerializerMethodField()
    recognition_cycle = serializers.SerializerMethodField()
    constitution_title = serializers.SerializerMethodField()
    directory_notes = serializers.SerializerMethodField()
    officers = serializers.SerializerMethodField()

    class Meta:
        model = Club
        fields = [
            "id", "name", "slug", "logo", "logo_initial", "category", "description",
            "mission", "vision", "objectives", "established_date", "status",
            "charter_statement",
            "public_contact_email", "public_contact_channels",
            "recognition_cycle", "constitution_title", "directory_notes", "officers",
            "institution_name", "institution_slug", "published_watch_count",
        ]
        read_only_fields = fields

    def _channels(self, obj):
        return obj.public_contact_channels or {}

    def get_logo_initial(self, obj):
        return (obj.name or "?")[:1].upper()

    def get_published_watch_count(self, obj):
        return getattr(obj, "published_watch_count", 0) or 0

    def get_recognition_cycle(self, obj):
        return self._channels(obj).get("cycle") or ""

    def get_constitution_title(self, obj):
        return self._channels(obj).get("constitution") or ""

    def get_directory_notes(self, obj):
        return self._channels(obj).get("notes") or ""

    def get_officers(self, obj):
        return self._channels(obj).get("officers") or []


class ClubManageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Club
        fields = [
            "id", "name", "slug", "logo", "category", "description",
            "mission", "vision", "objectives", "established_date", "status",
            "public_contact_email", "public_contact_channels",
            "charter_statement", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "status", "created_at", "updated_at"]


class ClubMembershipSerializer(serializers.ModelSerializer):
    club_name = serializers.CharField(source="club.name", read_only=True)
    user_name = serializers.SerializerMethodField()
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = ClubMembership
        fields = [
            "id", "club", "club_name", "user", "user_name", "user_email",
            "role", "status", "source", "is_active", "joined_at", "left_at",
        ]
        read_only_fields = ["id", "status", "source", "user", "is_active", "joined_at", "left_at"]

    def get_user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username


class LeadershipTermSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadershipTerm
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]


class LeadershipHandoverSerializer(serializers.ModelSerializer):
    club_name = serializers.CharField(source="club.name", read_only=True)
    outgoing_name = serializers.SerializerMethodField()
    incoming_name = serializers.SerializerMethodField()
    submitted_by_email = serializers.EmailField(source="outgoing.email", read_only=True)

    class Meta:
        model = LeadershipHandover
        fields = [
            "id",
            "club",
            "club_name",
            "outgoing",
            "outgoing_name",
            "submitted_by_email",
            "incoming",
            "incoming_name",
            "incoming_email",
            "outgoing_committee",
            "incoming_committee",
            "academic_year",
            "notes",
            "achievements_summary",
            "status",
            "confirmed_by",
            "confirmed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "outgoing",
            "incoming",
            "status",
            "confirmed_by",
            "confirmed_at",
            "created_at",
            "updated_at",
            "club_name",
            "outgoing_name",
            "incoming_name",
            "submitted_by_email",
            "academic_year",
            "incoming_email",
        ]

    def get_outgoing_name(self, obj):
        return obj.outgoing.get_full_name() or obj.outgoing.username

    def get_incoming_name(self, obj):
        if not obj.incoming_id:
            return ""
        return obj.incoming.get_full_name() or obj.incoming.username


class ClubConceptNoteSerializer(serializers.ModelSerializer):
    club_name = serializers.CharField(source="club.name", read_only=True)
    submitted_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ClubConceptNote
        fields = [
            "id",
            "club",
            "club_name",
            "submitted_by",
            "submitted_by_name",
            "academic_year",
            "title",
            "purpose",
            "amount_requested",
            "status",
            "committee_comment",
            "decided_by",
            "decided_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "submitted_by",
            "academic_year",
            "status",
            "committee_comment",
            "decided_by",
            "decided_at",
            "created_at",
            "club_name",
            "submitted_by_name",
        ]

    def get_submitted_by_name(self, obj):
        return obj.submitted_by.get_full_name() or obj.submitted_by.username


class ClubBudgetSpendSerializer(serializers.ModelSerializer):
    club_name = serializers.CharField(source="club.name", read_only=True)

    class Meta:
        model = ClubBudgetSpend
        fields = [
            "id",
            "club",
            "club_name",
            "concept_note",
            "recorded_by",
            "academic_year",
            "amount",
            "comment",
            "spent_on",
            "created_at",
        ]
        read_only_fields = ["id", "recorded_by", "academic_year", "created_at", "club_name"]
