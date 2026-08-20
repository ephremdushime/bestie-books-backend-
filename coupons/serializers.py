from rest_framework import serializers

from .models import Coupon


class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = (
            "id", "code", "discount_type", "discount_value", "max_uses",
            "used_count", "valid_from", "valid_until", "is_active",
        )
        read_only_fields = ("id", "used_count")
