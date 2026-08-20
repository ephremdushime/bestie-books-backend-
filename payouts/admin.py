from django.contrib import admin

from .models import PayoutRequest


@admin.register(PayoutRequest)
class PayoutRequestAdmin(admin.ModelAdmin):
    list_display = ("author", "amount", "currency", "status", "created_at", "processed_at")
    list_filter = ("status",)
    search_fields = ("author__pen_name", "author__user__email")
