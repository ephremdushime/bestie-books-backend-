"""
MTN MoMo integration tests. Mocks MTN's HTTP API with `responses` since
this environment can't reach sandbox.momodeveloper.mtn.com directly - the
mocks assert the exact request shape (headers, URL, payload) MTN's docs
specify, so a pass here means the client is wired correctly against the
real spec, not just against itself.
"""

import responses
from django.test import TestCase, override_settings

from accounts.models import AuthorProfile, User
from catalog.models import Book, Category
from orders.models import LibraryEntry, Order, OrderItem
from .models import Payment
from .momo_client import MomoClient
from .services import initiate_momo_payment, check_momo_status

MOMO_SETTINGS = dict(
    MOMO_BASE_URL="https://sandbox.momodeveloper.mtn.com",
    MOMO_TARGET_ENVIRONMENT="sandbox",
    MOMO_SUBSCRIPTION_KEY="test-subscription-key",
    MOMO_API_USER="test-api-user",
    MOMO_API_KEY="test-api-key",
    MOMO_CALLBACK_URL="",
)


@override_settings(**MOMO_SETTINGS)
class MomoClientTests(TestCase):
    @responses.activate
    def test_get_access_token(self):
        responses.add(
            responses.POST,
            "https://sandbox.momodeveloper.mtn.com/collection/token/",
            json={"access_token": "abc123", "token_type": "access_token", "expires_in": 3600},
            status=200,
        )
        client = MomoClient()
        token = client.get_access_token()
        self.assertEqual(token, "abc123")

        sent = responses.calls[0].request
        self.assertEqual(sent.headers["Ocp-Apim-Subscription-Key"], "test-subscription-key")
        self.assertTrue(sent.headers["Authorization"].startswith("Basic "))

    @responses.activate
    def test_request_to_pay_sends_correct_shape(self):
        responses.add(
            responses.POST,
            "https://sandbox.momodeveloper.mtn.com/collection/token/",
            json={"access_token": "abc123"},
            status=200,
        )
        responses.add(
            responses.POST,
            "https://sandbox.momodeveloper.mtn.com/collection/v1_0/requesttopay",
            status=202,
        )

        client = MomoClient()
        reference_id = client.request_to_pay(
            amount="5.00", currency="EUR", msisdn="+250788000000",
            external_id="order-123", payer_message="Bestie Books order",
        )
        self.assertTrue(reference_id)

        pay_request = responses.calls[1].request
        self.assertEqual(pay_request.headers["X-Reference-Id"], reference_id)
        self.assertEqual(pay_request.headers["X-Target-Environment"], "sandbox")
        self.assertTrue(pay_request.headers["Authorization"].startswith("Bearer "))
        import json
        body = json.loads(pay_request.body)
        self.assertEqual(body["payer"]["partyId"], "250788000000")  # '+' stripped
        self.assertEqual(body["amount"], "5.00")

    @responses.activate
    def test_get_transaction_status(self):
        responses.add(
            responses.POST,
            "https://sandbox.momodeveloper.mtn.com/collection/token/",
            json={"access_token": "abc123"},
            status=200,
        )
        responses.add(
            responses.GET,
            "https://sandbox.momodeveloper.mtn.com/collection/v1_0/requesttopay/ref-1",
            json={"status": "SUCCESSFUL", "financialTransactionId": "999"},
            status=200,
        )
        client = MomoClient()
        result = client.get_transaction_status("ref-1")
        self.assertEqual(result["status"], "SUCCESSFUL")


@override_settings(**MOMO_SETTINGS)
class MomoPaymentFlowTests(TestCase):
    """Exercises the Payment model + services against the mocked client."""

    def setUp(self):
        self.reader = User.objects.create_user(
            email="reader@test.rw", password="pw", role=User.Role.READER
        )
        author_user = User.objects.create_user(
            email="author@test.rw", password="pw", role=User.Role.AUTHOR
        )
        author = AuthorProfile.objects.create(user=author_user, pen_name="Test Author")
        category = Category.objects.create(name="Fiction")
        self.book = Book.objects.create(
            author=author, category=category, title="Test Book",
            price="5.00", currency="EUR", status=Book.Status.PUBLISHED,
        )
        self.order = Order.objects.create(user=self.reader, currency="EUR", total_amount="5.00")
        OrderItem.objects.create(order=self.order, book=self.book, unit_price="5.00")

    @responses.activate
    def test_initiate_then_confirm_unlocks_library(self):
        responses.add(
            responses.POST,
            "https://sandbox.momodeveloper.mtn.com/collection/token/",
            json={"access_token": "abc123"}, status=200,
        )
        responses.add(
            responses.POST,
            "https://sandbox.momodeveloper.mtn.com/collection/v1_0/requesttopay",
            status=202,
        )
        payment = Payment.objects.create(
            order=self.order, provider=Payment.Provider.MTN_MOMO,
            phone_number="+250788000000", amount="5.00", currency="EUR",
        )
        payment = initiate_momo_payment(payment)
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertTrue(payment.external_reference)

        responses.add(
            responses.POST,
            "https://sandbox.momodeveloper.mtn.com/collection/token/",
            json={"access_token": "abc123"}, status=200,
        )
        responses.add(
            responses.GET,
            f"https://sandbox.momodeveloper.mtn.com/collection/v1_0/requesttopay/{payment.external_reference}",
            json={"status": "SUCCESSFUL", "financialTransactionId": "999"}, status=200,
        )
        payment = check_momo_status(payment)

        self.assertEqual(payment.status, Payment.Status.SUCCESS)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)
        self.assertTrue(LibraryEntry.objects.filter(user=self.reader, book=self.book).exists())

    @responses.activate
    def test_initiate_then_failed_status_does_not_unlock(self):
        responses.add(
            responses.POST,
            "https://sandbox.momodeveloper.mtn.com/collection/token/",
            json={"access_token": "abc123"}, status=200,
        )
        responses.add(
            responses.POST,
            "https://sandbox.momodeveloper.mtn.com/collection/v1_0/requesttopay",
            status=202,
        )
        payment = Payment.objects.create(
            order=self.order, provider=Payment.Provider.MTN_MOMO,
            phone_number="+250788000000", amount="5.00", currency="EUR",
        )
        payment = initiate_momo_payment(payment)

        responses.add(
            responses.POST,
            "https://sandbox.momodeveloper.mtn.com/collection/token/",
            json={"access_token": "abc123"}, status=200,
        )
        responses.add(
            responses.GET,
            f"https://sandbox.momodeveloper.mtn.com/collection/v1_0/requesttopay/{payment.external_reference}",
            json={"status": "FAILED", "reason": "PAYER_NOT_FOUND"}, status=200,
        )
        payment = check_momo_status(payment)

        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertFalse(LibraryEntry.objects.filter(user=self.reader, book=self.book).exists())

    @responses.activate
    def test_momo_api_error_marks_payment_failed(self):
        responses.add(
            responses.POST,
            "https://sandbox.momodeveloper.mtn.com/collection/token/",
            json={"error": "invalid_client"}, status=401,
        )
        payment = Payment.objects.create(
            order=self.order, provider=Payment.Provider.MTN_MOMO,
            phone_number="+250788000000", amount="5.00", currency="EUR",
        )
        payment = initiate_momo_payment(payment)
        self.assertEqual(payment.status, Payment.Status.FAILED)


AIRTEL_SETTINGS = dict(
    AIRTEL_BASE_URL="https://openapiuat.airtel.africa",
    AIRTEL_CLIENT_ID="test-client-id",
    AIRTEL_CLIENT_SECRET="test-client-secret",
    AIRTEL_COUNTRY="RW",
    AIRTEL_CURRENCY="RWF",
)


@override_settings(**AIRTEL_SETTINGS)
class AirtelPaymentFlowTests(TestCase):
    def setUp(self):
        self.reader = User.objects.create_user(
            email="reader.airtel@test.rw", password="pw", role=User.Role.READER
        )
        author_user = User.objects.create_user(
            email="author.airtel@test.rw", password="pw", role=User.Role.AUTHOR
        )
        author = AuthorProfile.objects.create(user=author_user, pen_name="Test Author")
        category = Category.objects.create(name="Fiction Airtel")
        self.book = Book.objects.create(
            author=author, category=category, title="Airtel Test Book",
            price="1500", currency="RWF", status=Book.Status.PUBLISHED,
        )
        self.order = Order.objects.create(user=self.reader, currency="RWF", total_amount="1500")
        OrderItem.objects.create(order=self.order, book=self.book, unit_price="1500")

    @responses.activate
    def test_initiate_then_success_unlocks_library(self):
        from .services import initiate_airtel_payment, check_airtel_status

        responses.add(
            responses.POST,
            "https://openapiuat.airtel.africa/auth/oauth2/token",
            json={"access_token": "tok123"}, status=200,
        )
        responses.add(
            responses.POST,
            "https://openapiuat.airtel.africa/merchant/v1/payments/",
            json={"data": {"transaction": {"id": "abc"}}, "status": {"success": True}}, status=200,
        )
        payment = Payment.objects.create(
            order=self.order, provider=Payment.Provider.AIRTEL_MONEY,
            phone_number="+250730000000", amount="1500", currency="RWF",
        )
        payment = initiate_airtel_payment(payment)
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertTrue(payment.external_reference)

        responses.add(
            responses.POST,
            "https://openapiuat.airtel.africa/auth/oauth2/token",
            json={"access_token": "tok123"}, status=200,
        )
        responses.add(
            responses.GET,
            f"https://openapiuat.airtel.africa/standard/v1/payments/{payment.external_reference}",
            json={"data": {"transaction": {"status": "TS"}}}, status=200,
        )
        payment = check_airtel_status(payment)

        self.assertEqual(payment.status, Payment.Status.SUCCESS)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)
        self.assertTrue(LibraryEntry.objects.filter(user=self.reader, book=self.book).exists())

    @responses.activate
    def test_initiate_then_failed_does_not_unlock(self):
        from .services import initiate_airtel_payment, check_airtel_status

        responses.add(
            responses.POST,
            "https://openapiuat.airtel.africa/auth/oauth2/token",
            json={"access_token": "tok123"}, status=200,
        )
        responses.add(
            responses.POST,
            "https://openapiuat.airtel.africa/merchant/v1/payments/",
            json={}, status=200,
        )
        payment = Payment.objects.create(
            order=self.order, provider=Payment.Provider.AIRTEL_MONEY,
            phone_number="+250730000000", amount="1500", currency="RWF",
        )
        payment = initiate_airtel_payment(payment)

        responses.add(
            responses.POST,
            "https://openapiuat.airtel.africa/auth/oauth2/token",
            json={"access_token": "tok123"}, status=200,
        )
        responses.add(
            responses.GET,
            f"https://openapiuat.airtel.africa/standard/v1/payments/{payment.external_reference}",
            json={"data": {"transaction": {"status": "TF"}}}, status=200,
        )
        payment = check_airtel_status(payment)

        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertFalse(LibraryEntry.objects.filter(user=self.reader, book=self.book).exists())


FLW_SETTINGS = dict(
    FLUTTERWAVE_BASE_URL="https://api.flutterwave.com",
    FLUTTERWAVE_SECRET_KEY="test-secret-key",
    FRONTEND_URL="http://localhost:3000",
)


@override_settings(**FLW_SETTINGS)
class FlutterwavePaymentFlowTests(TestCase):
    def setUp(self):
        self.reader = User.objects.create_user(
            email="reader.flw@test.rw", password="pw", role=User.Role.READER
        )
        author_user = User.objects.create_user(
            email="author.flw@test.rw", password="pw", role=User.Role.AUTHOR
        )
        author = AuthorProfile.objects.create(user=author_user, pen_name="Test Author")
        category = Category.objects.create(name="Fiction Flutterwave")
        self.book = Book.objects.create(
            author=author, category=category, title="Flutterwave Test Book",
            price="10.00", currency="USD", status=Book.Status.PUBLISHED,
        )
        self.order = Order.objects.create(user=self.reader, currency="USD", total_amount="10.00")
        OrderItem.objects.create(order=self.order, book=self.book, unit_price="10.00")

    @responses.activate
    def test_initiate_returns_checkout_link(self):
        from .services import initiate_flutterwave_payment

        responses.add(
            responses.POST,
            "https://api.flutterwave.com/v3/payments",
            json={"status": "success", "data": {"link": "https://checkout.flutterwave.com/pay/abc123"}},
            status=200,
        )
        payment = Payment.objects.create(
            order=self.order, provider=Payment.Provider.FLUTTERWAVE,
            amount="10.00", currency="USD",
        )
        payment = initiate_flutterwave_payment(payment)

        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertEqual(payment.checkout_url, "https://checkout.flutterwave.com/pay/abc123")
        self.assertEqual(payment.external_reference, str(payment.id))

        sent = responses.calls[0].request
        self.assertTrue(sent.headers["Authorization"].startswith("Bearer "))

    @responses.activate
    def test_verify_success_unlocks_library(self):
        from .services import initiate_flutterwave_payment, check_flutterwave_status

        responses.add(
            responses.POST,
            "https://api.flutterwave.com/v3/payments",
            json={"status": "success", "data": {"link": "https://checkout.flutterwave.com/pay/abc123"}},
            status=200,
        )
        payment = Payment.objects.create(
            order=self.order, provider=Payment.Provider.FLUTTERWAVE,
            amount="10.00", currency="USD",
        )
        payment = initiate_flutterwave_payment(payment)

        responses.add(
            responses.GET,
            "https://api.flutterwave.com/v3/transactions/verify_by_reference",
            json={"status": "success", "data": {"status": "successful", "amount": 10.00, "currency": "USD"}},
            status=200,
        )
        payment = check_flutterwave_status(payment)

        self.assertEqual(payment.status, Payment.Status.SUCCESS)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)
        self.assertTrue(LibraryEntry.objects.filter(user=self.reader, book=self.book).exists())

    @responses.activate
    def test_verify_amount_mismatch_does_not_confirm(self):
        """An underpayment reported as 'successful' must not unlock the library."""
        from .services import initiate_flutterwave_payment, check_flutterwave_status

        responses.add(
            responses.POST,
            "https://api.flutterwave.com/v3/payments",
            json={"status": "success", "data": {"link": "https://checkout.flutterwave.com/pay/abc123"}},
            status=200,
        )
        payment = Payment.objects.create(
            order=self.order, provider=Payment.Provider.FLUTTERWAVE,
            amount="10.00", currency="USD",
        )
        payment = initiate_flutterwave_payment(payment)

        responses.add(
            responses.GET,
            "https://api.flutterwave.com/v3/transactions/verify_by_reference",
            json={"status": "success", "data": {"status": "successful", "amount": 1.00, "currency": "USD"}},
            status=200,
        )
        payment = check_flutterwave_status(payment)

        self.assertNotEqual(payment.status, Payment.Status.SUCCESS)
        self.assertFalse(LibraryEntry.objects.filter(user=self.reader, book=self.book).exists())

    @responses.activate
    def test_verify_failed_does_not_unlock(self):
        from .services import initiate_flutterwave_payment, check_flutterwave_status

        responses.add(
            responses.POST,
            "https://api.flutterwave.com/v3/payments",
            json={"status": "success", "data": {"link": "https://checkout.flutterwave.com/pay/abc123"}},
            status=200,
        )
        payment = Payment.objects.create(
            order=self.order, provider=Payment.Provider.FLUTTERWAVE,
            amount="10.00", currency="USD",
        )
        payment = initiate_flutterwave_payment(payment)

        responses.add(
            responses.GET,
            "https://api.flutterwave.com/v3/transactions/verify_by_reference",
            json={"status": "success", "data": {"status": "failed", "amount": 10.00, "currency": "USD"}},
            status=200,
        )
        payment = check_flutterwave_status(payment)

        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertFalse(LibraryEntry.objects.filter(user=self.reader, book=self.book).exists())
