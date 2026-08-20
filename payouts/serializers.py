from rest_framework import serializers

from .models import PayoutRequest
from .services import available_balance


class PayoutRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayoutRequest
        fields = ("id", "amount", "currency", "status", "note", "processed_at", "created_at")
        read_only_fields = ("id", "status", "note", "processed_at", "created_at")

    def validate_amount(self, value):
        request = self.context["request"]
        author_profile = getattr(request.user, "author_profile", None)
        if author_profile is None:
            raise serializers.ValidationError("No author profile for this account.")
        balance = available_balance(author_profile)
        if value > balance:
            raise serializers.ValidationError(
                f"Requested amount exceeds your available balance ({balance:.2f})."
            )
        return value

    def create(self, validated_data):
        author_profile = self.context["request"].user.author_profile
        return PayoutRequest.objects.create(author=author_profile, **validated_data)
