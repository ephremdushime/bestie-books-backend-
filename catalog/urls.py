from rest_framework.routers import DefaultRouter

from .views import CategoryViewSet, BookViewSet

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("books", BookViewSet, basename="book")

urlpatterns = router.urls
