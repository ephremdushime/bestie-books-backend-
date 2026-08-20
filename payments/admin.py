from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "provider", "status", "amount", "currency", "created_at")
    list_filter = ("provider", "status")
    search_fields = ("order__user__email", "external_reference")
