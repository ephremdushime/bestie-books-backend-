from django.contrib import admin

from .models import ReadingSession, PageAccessLog, Bookmark, Highlight


class PageAccessLogInline(admin.TabularInline):
    model = PageAccessLog
    extra = 0
    readonly_fields = ("page_number", "ip_address", "accessed_at")
    can_delete = False


@admin.register(ReadingSession)
class ReadingSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "book", "started_at", "expires_at", "is_revoked", "last_ip")
    list_filter = ("is_revoked",)
    search_fields = ("user__email", "book__title")
    inlines = [PageAccessLogInline]


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ("user", "book", "page_number", "label")
    search_fields = ("user__email", "book__title")


@admin.register(Highlight)
class HighlightAdmin(admin.ModelAdmin):
    list_display = ("user", "book", "page_number", "color")
    list_filter = ("color",)
    search_fields = ("user__email", "book__title", "excerpt_text")
