from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import User, AuthorProfile, Device


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id", "email", "full_name", "phone_number", "country",
            "role", "is_verified", "date_joined",
        )
        read_only_fields = ("id", "role", "is_verified", "date_joined")


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    # A reader can self-register as an author; admin accounts are never
    # created through this public endpoint.
    role = serializers.ChoiceField(
        choices=[User.Role.READER, User.Role.AUTHOR], default=User.Role.READER
    )

    class Meta:
        model = User
        fields = ("email", "password", "full_name", "phone_number", "country", "role")

    def create(self, validated_data):
        password = validated_data.pop("password")
        role = validated_data.pop("role", User.Role.READER)
        user = User(role=role, **validated_data)
        user.set_password(password)
        user.save()
        if role == User.Role.AUTHOR:
            AuthorProfile.objects.create(user=user, pen_name=user.full_name)
        return user


class AuthorProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = AuthorProfile
        fields = ("id", "user", "pen_name", "bio", "payout_method", "is_approved")
        read_only_fields = ("id", "is_approved")


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = (
            "id", "device_id", "device_name", "device_type",
            "is_active", "is_verified", "last_seen_at",
        )
        read_only_fields = ("id", "is_verified", "last_seen_at")
