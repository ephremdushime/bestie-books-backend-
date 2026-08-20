from rest_framework import serializers

from catalog.models import Book
from .models import Order, OrderItem, LibraryEntry


class OrderItemSerializer(serializers.ModelSerializer):
    title = serializers.CharField(source="book.title", read_only=True)

    class Meta:
        model = OrderItem
        fields = ("id", "book", "title", "unit_price", "quantity")
        read_only_fields = ("id", "unit_price")


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    coupon_code = serializers.CharField(source="coupon.code", read_only=True, default=None)

    class Meta:
        model = Order
        fields = (
            "id", "status", "currency", "total_amount", "discount_amount",
            "coupon_code", "items", "created_at", "paid_at",
        )
        read_only_fields = fields


class CreateOrderSerializer(serializers.Serializer):
    """Accepts a list of book IDs (a multi-item cart) and an optional
    coupon code, and builds the Order + OrderItems."""

    book_ids = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=False, min_length=1
    )
    coupon_code = serializers.CharField(required=False, allow_blank=True)

    def validate_book_ids(self, value):
        books = Book.objects.filter(id__in=value, status=Book.Status.PUBLISHED)
        if books.count() != len(set(value)):
            raise serializers.ValidationError(
                "One or more books are unavailable or do not exist."
            )
        return value

    def validate_coupon_code(self, value):
        if not value:
            return value
        from coupons.models import Coupon
        try:
            coupon = Coupon.objects.get(code__iexact=value)
        except Coupon.DoesNotExist:
            raise serializers.ValidationError("That coupon code doesn't exist.")
        if not coupon.is_valid_now():
            raise serializers.ValidationError("That coupon is no longer valid.")
        self._coupon = coupon
        return value

    def create(self, validated_data):
        user = self.context["request"].user
        books = Book.objects.filter(id__in=validated_data["book_ids"])

        order = Order.objects.create(
            user=user,
            currency=books.first().currency,
            coupon=getattr(self, "_coupon", None),
        )
        for book in books:
            OrderItem.objects.create(
                order=order, book=book, unit_price=book.price, quantity=1
            )
        order.recalculate_total()
        return order


class LibraryEntrySerializer(serializers.ModelSerializer):
    book_title = serializers.CharField(source="book.title", read_only=True)
    cover_image = serializers.ImageField(source="book.cover_image", read_only=True)

    class Meta:
        model = LibraryEntry
        fields = (
            "id", "book", "book_title", "cover_image",
            "unlocked_at", "last_read_at", "reading_progress_percent",
        )
        read_only_fields = fields
