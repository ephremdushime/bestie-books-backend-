from rest_framework.routers import DefaultRouter

from .views import PayoutRequestViewSet

router = DefaultRouter()
router.register("payouts", PayoutRequestViewSet, basename="payout")

urlpatterns = router.urls
