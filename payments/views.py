from rest_framework import viewsets, permissions, mixins
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from accounts.permissions import IsAdminRole
from .models import Payment
from .serializers import PaymentSerializer, InitiatePaymentSerializer
from .services import confirm_payment, fail_payment, check_momo_status, check_airtel_status, check_flutterwave_status


class PaymentViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                      mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == user.Role.ADMIN or user.is_staff:
            qs = Payment.objects.all()
        else:
            qs = Payment.objects.filter(order__user=user)
        order_id = self.request.query_params.get("order")
        if order_id:
            qs = qs.filter(order_id=order_id)
        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return InitiatePaymentSerializer
        return PaymentSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        payment = serializer.save()
        return Response(PaymentSerializer(payment).data, status=201)

    @action(detail=True, methods=["post"])
    def check_status(self, request, pk=None):
        """
        Poll the provider for the current status of a pending payment.
        The reader's client should call this (e.g. after the MTN MoMo
        prompt appears on their phone) instead of waiting indefinitely -
        MTN's async callback (see momo_webhook below) covers the case
        where the client isn't polling at all.
        """
        payment = self.get_object()
        is_admin = request.user.role == request.user.Role.ADMIN or request.user.is_staff
        if payment.order.user != request.user and not is_admin:
            raise PermissionDenied("Not your payment.")

        if payment.provider == Payment.Provider.MTN_MOMO:
            payment = check_momo_status(payment)
        elif payment.provider == Payment.Provider.AIRTEL_MONEY:
            payment = check_airtel_status(payment)
        elif payment.provider == Payment.Provider.FLUTTERWAVE:
            payment = check_flutterwave_status(payment)
        return Response(PaymentSerializer(payment).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminRole])
    def simulate_confirm(self, request, pk=None):
        """
        DEV-ONLY STUB: manually flips a payment to SUCCESS and unlocks the
        library - still useful for providers without a sandbox at hand
        (Airtel Money, cards). For MTN MoMo, prefer check_status or the
        real webhook, which exercise the actual integration.
        """
        payment = self.get_object()
        confirm_payment(payment, external_reference=f"SIMULATED-{payment.id}")
        return Response(PaymentSerializer(payment).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminRole])
    def simulate_fail(self, request, pk=None):
        payment = self.get_object()
        fail_payment(payment)
        return Response(PaymentSerializer(payment).data)


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def momo_webhook(request):
    """
    Receives MTN's async callback to the X-Callback-Url set on the
    original requesttopay call (settings.MOMO_CALLBACK_URL). Requires a
    publicly reachable HTTPS URL, so it's inert in local/sandbox dev -
    check_status above is the path exercised by this scaffold.

    NOTE: MTN's sandbox callback payload isn't signed, so in production
    this endpoint should also be locked down (IP allowlist and/or a
    shared secret in the URL) before going live - left as a TODO here.
    """
    reference_id = request.data.get("referenceId") or request.data.get("externalId")
    momo_status = request.data.get("status")

    payment = Payment.objects.filter(
        provider=Payment.Provider.MTN_MOMO, external_reference=reference_id
    ).first()
    if payment is None:
        return Response({"detail": "Unknown payment reference"}, status=404)

    if momo_status == "SUCCESSFUL":
        confirm_payment(payment, external_reference=reference_id, raw_response=request.data)
    elif momo_status == "FAILED":
        fail_payment(payment, raw_response=request.data)

    return Response({"received": True})


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def flutterwave_webhook(request):
    """
    Receives Flutterwave's webhook. Unlike MTN's callback, Flutterwave
    signs these with a shared secret in the `verif-hash` header - we
    reject anything that doesn't match FLUTTERWAVE_WEBHOOK_SECRET_HASH
    rather than trusting the payload on its face.
    """
    from django.conf import settings

    signature = request.headers.get("verif-hash", "")
    if not settings.FLUTTERWAVE_WEBHOOK_SECRET_HASH or signature != settings.FLUTTERWAVE_WEBHOOK_SECRET_HASH:
        return Response({"detail": "Invalid signature"}, status=401)

    data = request.data.get("data", {})
    tx_ref = data.get("tx_ref")
    status = data.get("status")

    payment = Payment.objects.filter(
        provider=Payment.Provider.FLUTTERWAVE, external_reference=tx_ref
    ).first()
    if payment is None:
        return Response({"detail": "Unknown payment reference"}, status=404)

    if status == "successful":
        confirm_payment(payment, external_reference=tx_ref, raw_response=data)
    elif status in ("failed", "cancelled"):
        fail_payment(payment, raw_response=data)

    return Response({"received": True})
