from rest_framework.routers import DefaultRouter

from .views import OrderViewSet, LibraryViewSet

router = DefaultRouter()
router.register("orders", OrderViewSet, basename="order")
router.register("library", LibraryViewSet, basename="library")

urlpatterns = router.urls
