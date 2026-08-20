from django.conf import settings
from django.db import models

from common.models import BaseModel


class Notification(BaseModel):
    """
    In-app notifications (protocol sec. 15). Email/push delivery would
    hang off the same `notify()` call site (notifications/services.py)
    once SMTP/FCM credentials exist - this scaffold implements the
    in-app feed only, which is also the one thing a frontend can render
    without any third-party credentials at all.
    """

    class Kind(models.TextChoices):
        PURCHASE_CONFIRMED = "purchase_confirmed", "Purchase confirmed"
        BOOK_APPROVED = "book_approved", "Book approved"
        BOOK_REJECTED = "book_rejected", "Book rejected"
        PAYOUT_UPDATE = "payout_update", "Payout update"
        REVIEW_RECEIVED = "review_received", "Review received"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=30, choices=Kind.choices)
    message = models.CharField(max_length=255)
    link = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        db_table = "notifications_notification"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email}: {self.message}"
