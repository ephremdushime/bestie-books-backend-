from django.contrib import admin

from .models import Order, OrderItem, LibraryEntry


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "total_amount", "currency", "created_at")
    list_filter = ("status", "currency")
    search_fields = ("user__email",)
    inlines = [OrderItemInline]


@admin.register(LibraryEntry)
class LibraryEntryAdmin(admin.ModelAdmin):
    list_display = ("user", "book", "unlocked_at", "reading_progress_percent")
    search_fields = ("user__email", "book__title")
