from django.contrib import admin

from .models import Category, Book, BookAsset


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "parent")
    prepopulated_fields = {"slug": ("name",)}


class BookAssetInline(admin.StackedInline):
    model = BookAsset
    extra = 0


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "category", "status", "price", "currency", "published_at")
    list_filter = ("status", "language", "category")
    search_fields = ("title", "keywords", "isbn", "author__pen_name")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [BookAssetInline]
