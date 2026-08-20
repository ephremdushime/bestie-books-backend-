from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User, AuthorProfile, Device


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ["-date_joined"]
    list_display = ("email", "full_name", "role", "is_verified", "is_active", "is_staff")
    list_filter = ("role", "is_verified", "is_active", "is_staff")
    search_fields = ("email", "full_name", "phone_number")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("full_name", "phone_number", "country")}),
        ("Role & status", {"fields": ("role", "is_active", "is_verified")}),
        ("Permissions", {"fields": ("is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2", "role")}),
    )


@admin.register(AuthorProfile)
class AuthorProfileAdmin(admin.ModelAdmin):
    list_display = ("pen_name", "user", "is_approved")
    list_filter = ("is_approved",)
    search_fields = ("pen_name", "user__email")


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("user", "device_name", "device_type", "is_active", "is_verified", "last_seen_at")
    list_filter = ("device_type", "is_active", "is_verified")
