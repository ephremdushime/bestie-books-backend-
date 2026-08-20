from django.utils import timezone
from django.db import models

from common.models import BaseModel


class Coupon(BaseModel):
    """Admin-managed discount codes, applied at order creation (protocol
    sec. 13 - Admin: Coupons; sec. 16 - conversion/revenue reporting)."""

    class DiscountType(models.TextChoices):
        PERCENT = "percent", "Percent off"
        FIXED = "fixed", "Fixed amount off"

    code = models.CharField(max_length=40, unique=True)
    discount_type = models.CharField(max_length=10, choices=DiscountType.choices)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    max_uses = models.PositiveIntegerField(null=True, blank=True, help_text="Blank = unlimited")
    used_count = models.PositiveIntegerField(default=0)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "coupons_coupon"

    def is_valid_now(self) -> bool:
        if not self.is_active:
            return False
        now = timezone.now()
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        if self.max_uses is not None and self.used_count >= self.max_uses:
            return False
        return True

    def compute_discount(self, subtotal) -> "float | int":
        if self.discount_type == self.DiscountType.PERCENT:
            return subtotal * (self.discount_value / 100)
        return min(self.discount_value, subtotal)

    def __str__(self):
        return self.code
