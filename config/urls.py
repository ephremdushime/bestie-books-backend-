from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("accounts.urls")),
    path("api/v1/", include("catalog.urls")),
    path("api/v1/", include("orders.urls")),
    path("api/v1/", include("payments.urls")),
    path("api/v1/reader/", include("reader.urls")),
    path("api/v1/", include("reviews.urls")),
    path("api/v1/", include("notifications.urls")),
    path("api/v1/", include("coupons.urls")),
    path("api/v1/", include("payouts.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
