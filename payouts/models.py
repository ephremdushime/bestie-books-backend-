from django.db import models

from common.models import BaseModel


class PayoutRequest(BaseModel):
    """
    Royalty payout requests (protocol sec. 3 - Author: 'Request payouts';
    sec. 12 - Author Dashboard: 'Payout requests'). Amount validated
    against payouts.services.available_balance at request time - see
    payouts/serializers.py.
    """

    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        PAID = "paid", "Paid"
        REJECTED = "rejected", "Rejected"

    author = models.ForeignKey(
        "accounts.AuthorProfile", on_delete=models.CASCADE, related_name="payout_requests"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.REQUESTED)
    note = models.CharField(max_length=255, blank=True, help_text="Admin note, e.g. rejection reason")
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "payouts_payout_request"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.author.pen_name}: {self.amount} {self.currency} ({self.status})"
