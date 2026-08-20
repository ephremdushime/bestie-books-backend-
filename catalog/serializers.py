from rest_framework import serializers

from accounts.serializers import AuthorProfileSerializer
from .models import Category, Book, BookAsset


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug", "parent")
        read_only_fields = ("id", "slug")


class BookAssetSerializer(serializers.ModelSerializer):
    """
    Deliberately excludes storage_key / encryption_key_ref from output -
    those are internal plumbing for the (future) secure reader service,
    never something a client should receive directly.
    """

    class Meta:
        model = BookAsset
        fields = ("id", "file_type", "original_filename", "page_count", "virus_scan_passed")
        read_only_fields = fields


class BookListSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.pen_name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Book
        fields = (
            "id", "title", "slug", "author", "author_name", "category", "category_name",
            "price", "currency", "cover_image", "status", "published_at",
        )
        read_only_fields = ("id", "slug", "status", "published_at")


class BookDetailSerializer(serializers.ModelSerializer):
    author = AuthorProfileSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    asset = BookAssetSerializer(read_only=True)

    class Meta:
        model = Book
        fields = (
            "id", "title", "slug", "description", "keywords", "language", "isbn",
            "cover_image", "price", "currency", "status", "published_at",
            "author", "category", "asset", "created_at",
        )
        read_only_fields = ("id", "slug", "status", "published_at", "created_at")


class BookWriteSerializer(serializers.ModelSerializer):
    """Used for author create/update - takes category as a plain FK id."""

    class Meta:
        model = Book
        fields = (
            "id", "title", "description", "keywords", "language", "isbn",
            "cover_image", "price", "currency", "category",
        )
        read_only_fields = ("id",)
