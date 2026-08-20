from rest_framework.routers import DefaultRouter

from django.urls import path

from .views import StartReadingSessionView, ReadPageView, BookmarkViewSet, HighlightViewSet

router = DefaultRouter()
router.register("bookmarks", BookmarkViewSet, basename="bookmark")
router.register("highlights", HighlightViewSet, basename="highlight")

urlpatterns = [
    path("sessions/", StartReadingSessionView.as_view(), name="reader-session-start"),
    path("read/<str:token>/pages/<int:page_number>/", ReadPageView.as_view(), name="reader-page"),
] + router.urls
