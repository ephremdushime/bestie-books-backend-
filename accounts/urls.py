from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import RegisterView, MeView, AuthorMeView, DeviceViewSet

router = DefaultRouter()
router.register("devices", DeviceViewSet, basename="device")

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/token/", TokenObtainPairView.as_view(), name="token-obtain-pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("users/me/", MeView.as_view(), name="user-me"),
    path("authors/me/", AuthorMeView.as_view(), name="author-me"),
] + router.urls
