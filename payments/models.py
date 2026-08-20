from django.db import models

from common.models import BaseModel


class Payment(BaseModel):
    """
    Tracks a payment attempt against an Order (protocol sec. 6).
    One Order can have multiple Payment rows if a first attempt fails
    and the reader retries with a different provider.
    """

    class Provider(models.TextChoices):
        MTN_MOMO = "mtn_momo", "MTN Mobile Money"
        AIRTEL_MONEY = "airtel_money", "Airtel Money"
        FLUTTERWAVE = "flutterwave", "Card / Bank Transfer (Flutterwave)"
        VISA = "visa", "Visa"
        MASTERCARD = "mastercard", "Mastercard"
        PAYPAL = "paypal", "PayPal"

    class Status(models.TextChoices):
        INITIATED = "initiated", "Initiated"
        PENDING = "pending", "Pending Confirmation"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    order = models.ForeignKey(
        "orders.Order", on_delete=models.CASCADE, related_name="payments"
    )
    provider = models.CharField(max_length=20, choices=Provider.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.INITIATED)

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="RWF")

    # Mobile money specific
    phone_number = models.CharField(max_length=20, blank=True)

    # Redirect-based providers (Flutterwave): the hosted checkout URL the
    # client should send the payer to. Empty for push-based providers.
    checkout_url = models.URLField(blank=True)

    # Reconciliation
    external_reference = models.CharField(
        max_length=255, blank=True, help_text="Transaction ID returned by the provider"
    )
    raw_response = models.JSONField(default=dict, blank=True)

    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "payments_payment"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["external_reference"]),
        ]

    def __str__(self):
        return f"{self.provider} - {self.amount} {self.currency} ({self.status})"
