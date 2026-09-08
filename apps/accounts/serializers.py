from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import User


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "role", "student_id", "phone_number", "avatar"]
        read_only_fields = ["id", "role"]  # role changes go through an authorized admin action, never self-service


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ["username", "email", "password", "first_name", "last_name", "student_id"]

    def create(self, validated_data):
        password = validated_data.pop("password")
        # Every self-registration lands as STUDENT — elevation to Club
        # Leader/Committee happens through an authorized workflow, never
        # through the public signup form (PRS Section 4 & 12).
        user = User(**validated_data, role=User.Role.STUDENT)
        user.set_password(password)
        user.save()
        return user


from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate


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
                user = authenticate(username=user_obj.username, password=password)

        if not user:
            raise serializers.ValidationError({"detail": "No active account found with the given credentials."})

        refresh = self.get_token(user)
        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "full_name": user.get_full_name() or user.username,
                "role": user.role,
                "student_id": user.student_id,
                "assigned_clubs": list(user.assigned_club_ids()),
            },
        }
