from rest_framework import serializers

from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = Review
        fields = (
            "id", "book", "user", "reviewer_name", "rating", "comment",
            "author_response", "responded_at", "created_at",
        )
        read_only_fields = ("id", "user", "reviewer_name", "author_response", "responded_at", "created_at")


class AuthorResponseSerializer(serializers.Serializer):
    author_response = serializers.CharField()
