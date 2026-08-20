from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import PaymentViewSet, momo_webhook, flutterwave_webhook

router = DefaultRouter()
router.register("payments", PaymentViewSet, basename="payment")

urlpatterns = [
    path("payments/webhooks/mtn-momo/", momo_webhook, name="momo-webhook"),
    path("payments/webhooks/flutterwave/", flutterwave_webhook, name="flutterwave-webhook"),
] + router.urls
