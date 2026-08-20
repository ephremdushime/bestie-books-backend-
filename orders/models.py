from django.conf import settings
from django.db import models

from common.models import BaseModel


class Order(BaseModel):
    """
    Protocol sec. 6: Customer -> Payment Gateway -> Verification -> Database
    -> Library Unlock. An Order is the "Database" step; it stays PENDING
    until payments.Payment confirms it, at which point LibraryEntry rows
    are created (the "Library Unlock" step).
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders"
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    currency = models.CharField(max_length=3, default="RWF")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    coupon = models.ForeignKey(
        "coupons.Coupon", on_delete=models.SET_NULL, null=True, blank=True, related_name="orders"
    )
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "orders_order"
        ordering = ["-created_at"]

    def recalculate_total(self):
        subtotal = sum(item.line_total for item in self.items.all())
        discount = 0
        if self.coupon and self.coupon.is_valid_now():
            discount = self.coupon.compute_discount(subtotal)
        else:
            self.coupon = None
        self.discount_amount = discount
        self.total_amount = max(subtotal - discount, 0)
        self.save(update_fields=["total_amount", "discount_amount", "coupon"])

    def __str__(self):
        return f"Order {self.id} ({self.user.email})"


class OrderItem(BaseModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    book = models.ForeignKey("catalog.Book", on_delete=models.PROTECT, related_name="order_items")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "orders_order_item"
        unique_together = ("order", "book")  # a book only needs to be purchased once per order

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.book.title} x{self.quantity}"


class LibraryEntry(BaseModel):
    """
    A reader's personalized cloud library (protocol sec. 2, sec. 11).
    Created only after payment confirmation - this row is what the
    reader-facing app checks to grant access to a book.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="library_entries"
    )
    book = models.ForeignKey("catalog.Book", on_delete=models.PROTECT, related_name="library_entries")
    order_item = models.ForeignKey(
        OrderItem, on_delete=models.SET_NULL, null=True, related_name="library_entries"
    )
    unlocked_at = models.DateTimeField(auto_now_add=True)
    last_read_at = models.DateTimeField(null=True, blank=True)
    reading_progress_percent = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "orders_library_entry"
        unique_together = ("user", "book")
        verbose_name_plural = "library entries"

    def __str__(self):
        return f"{self.user.email} owns {self.book.title}"
