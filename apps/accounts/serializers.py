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
