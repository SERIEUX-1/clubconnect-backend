from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Institution, User, institution_for_email, LicenceInquiry, SupportTicket, CampusCommitteeHandover


class InstitutionPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Institution
        fields = [
            "id",
            "name",
            "short_name",
            "slug",
            "kind",
            "country",
            "city",
            "awards_enabled",
            "awards_program_name",
            "allowed_email_domains",
            "student_email_domains",
            "staff_email_domains",
            "logo_url",
            "primary_color",
            "membership_census_open",
            "member_grant_amount",
            "member_grant_currency",
            "academic_year",
        ]

    academic_year = serializers.SerializerMethodField()

    def get_academic_year(self, obj):
        return obj.current_academic_year()


class CampusUserSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    active = serializers.BooleanField(source="is_active")

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "name",
            "role",
            "student_id",
            "is_active",
            "active",
        ]
        read_only_fields = ["id", "username", "email", "name"]

    def get_name(self, obj):
        return obj.get_full_name() or obj.username


class CampusInstitutionSerializer(serializers.ModelSerializer):
    academic_year = serializers.SerializerMethodField()

    class Meta:
        model = Institution
        fields = [
            "id",
            "name",
            "short_name",
            "slug",
            "kind",
            "student_email_domains",
            "staff_email_domains",
            "awards_enabled",
            "awards_program_name",
            "logo_url",
            "primary_color",
            "is_active",
            "academic_year_start_month",
            "academic_year_label",
            "academic_year",
            "report_deadline_day",
            "privacy_contact_email",
            "membership_census_open",
            "member_grant_amount",
            "member_grant_currency",
        ]
        read_only_fields = [
            "id",
            "slug",
            "kind",
            "is_active",
            "academic_year",
            "membership_census_open",
            "member_grant_amount",
            "member_grant_currency",
        ]

    def get_academic_year(self, obj):
        return obj.current_academic_year()


class UserProfileSerializer(serializers.ModelSerializer):
    institution = InstitutionPublicSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "student_id",
            "phone_number",
            "avatar",
            "institution",
            "preferred_language",
        ]
        read_only_fields = ["id", "role", "institution"]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = ["username", "email", "password", "first_name", "last_name", "student_id"]

    def validate_email(self, value):
        email = value.strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        institution = institution_for_email(email)
        if not institution:
            raise serializers.ValidationError(
                "This email is not from an institution licensed to use ClubConnect. "
                "Ask your campus to request a licence from the ClubConnect home page, "
                "or use your official school or staff email if you are already licensed."
            )
        return email

    def validate(self, attrs):
        email = attrs["email"]
        username = (attrs.get("username") or "").strip()
        if not username:
            username = email.split("@")[0].replace(".", "_")[:140]
        base = username
        n = 1
        while User.objects.filter(username__iexact=username).exists():
            username = f"{base}{n}"
            n += 1
        attrs["username"] = username
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        institution = institution_for_email(validated_data["email"])
        user = User(**validated_data, role=institution.role_for_new_account(validated_data["email"]), institution=institution)
        user.set_password(password)
        user.save()
        return user

    def to_representation(self, instance):
        return instance.public_identity()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = "username"

    def validate(self, attrs):
        login_id = attrs.get("username", "").strip()
        password = attrs.get("password")

        user = None
        if login_id:
            user_obj = (
                User.objects.filter(email__iexact=login_id).first()
                or User.objects.filter(username__iexact=login_id).first()
            )
            if user_obj:
                if user_obj.institution and not user_obj.institution.is_active:
                    raise serializers.ValidationError(
                        {"detail": "This institution no longer has access to ClubConnect."}
                    )
                user = authenticate(username=user_obj.username, password=password)

        if not user:
            raise serializers.ValidationError(
                {"detail": "No active account found with the given credentials."}
            )

        refresh = self.get_token(user)
        previous_login = user.last_login
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])
        identity = user.public_identity()
        identity["catch_up_since"] = previous_login.isoformat() if previous_login else None
        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": identity,
            "catch_up_since": identity["catch_up_since"],
        }


class LicenceInquirySerializer(serializers.ModelSerializer):
    class Meta:
        model = LicenceInquiry
        fields = [
            "id",
            "institution_name",
            "country",
            "city",
            "kind",
            "contact_name",
            "contact_role",
            "contact_email",
            "contact_phone",
            "student_email_domain",
            "staff_email_domain",
            "message",
            "status",
            "operator_notes",
            "created_at",
        ]
        read_only_fields = ["id", "status", "operator_notes", "created_at"]

    def validate_contact_email(self, value):
        return value.strip().lower()

    def validate_institution_name(self, value):
        name = (value or "").strip()
        if len(name) < 3:
            raise serializers.ValidationError("Tell us the name of the institution.")
        return name

    def _clean_domain(self, value):
        return str(value or "").lower().strip().lstrip("@")

    def validate(self, attrs):
        attrs["student_email_domain"] = self._clean_domain(attrs.get("student_email_domain"))
        attrs["staff_email_domain"] = self._clean_domain(attrs.get("staff_email_domain"))
        return attrs


class LicenceInquiryStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = LicenceInquiry
        fields = ["id", "status", "operator_notes"]


class SupportTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicket
        fields = [
            "id",
            "name",
            "email",
            "category",
            "subject",
            "body",
            "language",
            "status",
            "created_at",
        ]
        read_only_fields = ["id", "status", "created_at"]
        extra_kwargs = {
            "name": {"required": False, "allow_blank": True},
            "email": {"required": False, "allow_blank": True},
        }

    def validate_email(self, value):
        return value.strip().lower()

    def validate_subject(self, value):
        subject = (value or "").strip()
        if len(subject) < 3:
            raise serializers.ValidationError("Please add a short subject.")
        return subject

    def validate_body(self, value):
        body = (value or "").strip()
        if len(body) < 10:
            raise serializers.ValidationError("Please describe the issue in a little more detail.")
        return body


class SupportTicketStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicket
        fields = ["id", "status", "operator_notes"]


class CampusCommitteeHandoverSerializer(serializers.ModelSerializer):
    outgoing_name = serializers.SerializerMethodField()
    incoming_name = serializers.SerializerMethodField()
    submitted_by_email = serializers.EmailField(source="outgoing.email", read_only=True)
    institution_name = serializers.CharField(source="institution.short_name", read_only=True)

    class Meta:
        model = CampusCommitteeHandover
        fields = [
            "id",
            "institution",
            "institution_name",
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
        read_only_fields = fields

    def get_outgoing_name(self, obj):
        return obj.outgoing.get_full_name() or obj.outgoing.username

    def get_incoming_name(self, obj):
        if not obj.incoming_id:
            return ""
        return obj.incoming.get_full_name() or obj.incoming.username
