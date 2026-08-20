from rest_framework import serializers

from orders.models import Order
from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = (
            "id", "order", "provider", "status", "amount", "currency",
            "phone_number", "checkout_url", "external_reference", "confirmed_at", "created_at",
        )
        read_only_fields = ("id", "status", "amount", "currency", "checkout_url", "external_reference", "confirmed_at", "created_at")


class InitiatePaymentSerializer(serializers.Serializer):
    """
    Kicks off a payment against a pending Order. amount/currency are taken
    from the Order itself (never trust a client-supplied amount).
    """

    order_id = serializers.UUIDField()
    provider = serializers.ChoiceField(choices=Payment.Provider.choices)
    phone_number = serializers.CharField(required=False, allow_blank=True)

    def validate_order_id(self, value):
        request = self.context["request"]
        try:
            order = Order.objects.get(id=value, user=request.user)
        except Order.DoesNotExist:
            raise serializers.ValidationError("Order not found.")
        if order.status != Order.Status.PENDING:
            raise serializers.ValidationError(f"Order is already {order.status}.")
        self._order = order
        return value

    def validate(self, attrs):
        provider = attrs["provider"]
        mobile_money = {Payment.Provider.MTN_MOMO, Payment.Provider.AIRTEL_MONEY}
        if provider in mobile_money and not attrs.get("phone_number"):
            raise serializers.ValidationError(
                {"phone_number": "Required for mobile money payments."}
            )
        return attrs

    def create(self, validated_data):
        order = self._order
        payment = Payment.objects.create(
            order=order,
            provider=validated_data["provider"],
            phone_number=validated_data.get("phone_number", ""),
            amount=order.total_amount,
            currency=order.currency,
            status=Payment.Status.INITIATED,
        )

        if payment.provider == Payment.Provider.MTN_MOMO:
            from .services import initiate_momo_payment
            payment = initiate_momo_payment(payment)
        elif payment.provider == Payment.Provider.AIRTEL_MONEY:
            from .services import initiate_airtel_payment
            payment = initiate_airtel_payment(payment)
        elif payment.provider == Payment.Provider.FLUTTERWAVE:
            from .services import initiate_flutterwave_payment
            payment = initiate_flutterwave_payment(payment)

        return payment
