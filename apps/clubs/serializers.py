from rest_framework import serializers

from .models import Club, ClubMembership, LeadershipTerm


class ClubPublicSerializer(serializers.ModelSerializer):
    """
    Used for the Discover Clubs directory and public portfolio view. Only
    fields that are safe for ANY authenticated user (including students
    from other clubs) are exposed here. Confidential fields
    (handover_notes_private, internal committee notes) simply don't exist
    on this serializer — omission, not a permission check, is the first
    line of defense (defense in depth per PRS Section 12).
    """

    class Meta:
        model = Club
        fields = [
            "id", "name", "slug", "logo", "category", "description",
            "mission", "vision", "objectives", "established_date", "status",
            "public_contact_email", "public_contact_channels",
        ]
        read_only_fields = fields


class ClubManageSerializer(serializers.ModelSerializer):
    """Used by Club Leaders (own club only, enforced in the viewset via
    IsOwnClubLeader) and Committee roles. Still excludes handover_notes_private
    from Club Leaders — that field is only writable by the leader who wrote
    it and only readable by Committee, handled at the view level."""

    class Meta:
        model = Club
        fields = [
            "id", "name", "slug", "logo", "category", "description",
            "mission", "vision", "objectives", "established_date", "status",
            "public_contact_email", "public_contact_channels", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "status", "created_at", "updated_at"]


class ClubMembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClubMembership
        fields = ["id", "club", "user", "role", "status", "is_active", "joined_at", "left_at"]
        read_only_fields = ["id", "status"]


class LeadershipTermSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadershipTerm
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]
