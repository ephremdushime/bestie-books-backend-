from django.db import models, transaction
from django.utils import timezone

from orders.models import Order, LibraryEntry
from .models import Payment
from .momo_client import MomoClient, MomoAPIError
from .airtel_client import AirtelClient, AirtelAPIError


@transaction.atomic
def confirm_payment(payment: Payment, external_reference: str, raw_response: dict | None = None):
    """
    The single place where a successful payment becomes real book access.
    Called by the (future) provider webhook once MTN/Airtel/card confirms
    the transaction. Protocol sec. 6: Verification -> Database -> Library
    Unlock - this function *is* that last step.
    """

    payment.status = Payment.Status.SUCCESS
    payment.external_reference = external_reference
    payment.raw_response = raw_response or {}
    payment.confirmed_at = timezone.now()
    payment.save()

    order = payment.order
    order.status = Order.Status.PAID
    order.paid_at = payment.confirmed_at
    order.save(update_fields=["status", "paid_at"])

    for item in order.items.select_related("book"):
        LibraryEntry.objects.get_or_create(
            user=order.user,
            book=item.book,
            defaults={"order_item": item},
        )

    if order.coupon_id:
        from coupons.models import Coupon
        Coupon.objects.filter(id=order.coupon_id).update(used_count=models.F("used_count") + 1)

    from notifications.services import notify
    from notifications.models import Notification
    titles = ", ".join(item.book.title for item in order.items.all())
    notify(
        order.user,
        Notification.Kind.PURCHASE_CONFIRMED,
        f"Payment confirmed — {titles} is now in your library.",
        link="/library",
    )

    return payment


def fail_payment(payment: Payment, raw_response: dict | None = None):
    payment.status = Payment.Status.FAILED
    payment.raw_response = raw_response or {}
    payment.save()

    order = payment.order
    order.status = Order.Status.FAILED
    order.save(update_fields=["status"])
    return payment


def initiate_momo_payment(payment: Payment) -> Payment:
    """
    Kicks off the MTN MoMo "request to pay" prompt on the payer's phone.
    Leaves the payment PENDING - MTN doesn't confirm synchronously, the
    payer has to approve on their handset. Call check_momo_status (or
    handle_momo_callback) afterwards to find out what happened.
    """
    client = MomoClient()
    try:
        reference_id = client.request_to_pay(
            amount=payment.amount,
            currency=payment.currency,
            msisdn=payment.phone_number,
            external_id=str(payment.order_id),
            payer_message=f"Bestie Books order {payment.order_id}",
            payee_note="Bestie Books purchase",
        )
    except MomoAPIError as exc:
        return fail_payment(payment, raw_response={"error": str(exc), "body": exc.response_body})

    payment.status = Payment.Status.PENDING
    payment.external_reference = reference_id
    payment.save(update_fields=["status", "external_reference"])
    return payment


def check_momo_status(payment: Payment) -> Payment:
    """
    Polls MTN for the current status of a PENDING momo payment and applies
    confirm_payment/fail_payment accordingly. Safe to call repeatedly -
    it's a no-op once the payment is already SUCCESS/FAILED.
    """
    if payment.status not in (Payment.Status.PENDING, Payment.Status.INITIATED):
        return payment
    if not payment.external_reference:
        return payment

    client = MomoClient()
    try:
        result = client.get_transaction_status(payment.external_reference)
    except MomoAPIError as exc:
        # Transient outage or bad credentials - leave the payment PENDING
        # so the caller can retry, but surface what went wrong.
        payment.raw_response = {"check_status_error": str(exc)}
        payment.save(update_fields=["raw_response"])
        return payment

    status = result.get("status")

    if status == "SUCCESSFUL":
        return confirm_payment(payment, external_reference=payment.external_reference, raw_response=result)
    if status == "FAILED":
        return fail_payment(payment, raw_response=result)

    # Still PENDING on MTN's side - store the latest raw response but
    # don't change status.
    payment.raw_response = result
    payment.save(update_fields=["raw_response"])
    return payment


def initiate_airtel_payment(payment: Payment) -> Payment:
    """Airtel Money equivalent of initiate_momo_payment - same shape, different client."""
    client = AirtelClient()
    try:
        transaction_id = client.request_to_pay(
            amount=payment.amount,
            msisdn=payment.phone_number,
            external_id=str(payment.order_id),
        )
    except AirtelAPIError as exc:
        return fail_payment(payment, raw_response={"error": str(exc), "body": exc.response_body})

    payment.status = Payment.Status.PENDING
    payment.external_reference = transaction_id
    payment.save(update_fields=["status", "external_reference"])
    return payment


def check_airtel_status(payment: Payment) -> Payment:
    """Poll Airtel for status. TS=success, TF=failed, TIP=still in progress."""
    if payment.status not in (Payment.Status.PENDING, Payment.Status.INITIATED):
        return payment
    if not payment.external_reference:
        return payment

    client = AirtelClient()
    try:
        result = client.get_transaction_status(payment.external_reference)
    except AirtelAPIError as exc:
        payment.raw_response = {"check_status_error": str(exc)}
        payment.save(update_fields=["raw_response"])
        return payment

    status_code = (
        result.get("data", {}).get("transaction", {}).get("status")
        or result.get("status")
    )

    if status_code == "TS":
        return confirm_payment(payment, external_reference=payment.external_reference, raw_response=result)
    if status_code == "TF":
        return fail_payment(payment, raw_response=result)

    payment.raw_response = result
    payment.save(update_fields=["raw_response"])
    return payment


def initiate_flutterwave_payment(payment: Payment) -> Payment:
    """
    Requests a Flutterwave hosted-checkout link. tx_ref is the Payment's
    own id, so verify_flutterwave_payment can look the attempt straight
    back up - no separate reference-mapping table needed.
    """
    from django.conf import settings
    from .flutterwave_client import FlutterwaveClient, FlutterwaveAPIError

    client = FlutterwaveClient()
    tx_ref = str(payment.id)
    redirect_url = f"{settings.FRONTEND_URL}/checkout/{payment.order_id}"
    try:
        link = client.initiate_payment(
            tx_ref=tx_ref,
            amount=payment.amount,
            currency=payment.currency,
            redirect_url=redirect_url,
            email=payment.order.user.email,
            phone_number=payment.phone_number,
            name=payment.order.user.full_name or payment.order.user.email,
        )
    except FlutterwaveAPIError as exc:
        return fail_payment(payment, raw_response={"error": str(exc), "body": exc.response_body})

    payment.status = Payment.Status.PENDING
    payment.external_reference = tx_ref
    payment.checkout_url = link
    payment.save(update_fields=["status", "external_reference", "checkout_url"])
    return payment


def check_flutterwave_status(payment: Payment) -> Payment:
    """Verify against Flutterwave - never trust the redirect alone."""
    from .flutterwave_client import FlutterwaveClient, FlutterwaveAPIError

    if payment.status not in (Payment.Status.PENDING, Payment.Status.INITIATED):
        return payment
    if not payment.external_reference:
        return payment

    client = FlutterwaveClient()
    try:
        result = client.verify_by_reference(payment.external_reference)
    except FlutterwaveAPIError as exc:
        payment.raw_response = {"check_status_error": str(exc)}
        payment.save(update_fields=["raw_response"])
        return payment

    status = result.get("status")
    # Defense in depth: confirm the amount/currency Flutterwave verified
    # actually matches what we charged for, not just that *some* payment
    # under this reference succeeded.
    try:
        amount_ok = (
            float(result.get("amount", 0)) >= float(payment.amount)
            and str(result.get("currency")) == payment.currency
        )
    except (TypeError, ValueError):
        amount_ok = False

    if status == "successful" and amount_ok:
        return confirm_payment(payment, external_reference=payment.external_reference, raw_response=result)
    if status in ("failed", "cancelled"):
        return fail_payment(payment, raw_response=result)

    payment.raw_response = result
    payment.save(update_fields=["raw_response"])
    return payment
