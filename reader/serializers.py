from rest_framework import serializers

from .models import ReadingSession, Bookmark, Highlight


class StartSessionSerializer(serializers.Serializer):
    book_id = serializers.UUIDField()
    device_id = serializers.CharField(required=False, allow_blank=True)


class ReadingSessionSerializer(serializers.ModelSerializer):
    page_count = serializers.IntegerField(source="book.asset.page_count", read_only=True)

    class Meta:
        model = ReadingSession
        fields = ("id", "token", "book", "page_count", "started_at", "expires_at")
        read_only_fields = fields


class BookmarkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bookmark
        fields = ("id", "book", "page_number", "label", "created_at")
        read_only_fields = ("id", "created_at")


class HighlightSerializer(serializers.ModelSerializer):
    class Meta:
        model = Highlight
        fields = ("id", "book", "page_number", "excerpt_text", "note", "color", "created_at")
        read_only_fields = ("id", "created_at")
