from django.conf import settings
from django.db import models
from django.utils.text import slugify

from common.models import BaseModel


class Category(BaseModel):
    """Book categories (protocol sec. 14). Self-referential for subcategories."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    parent = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children"
    )

    class Meta:
        db_table = "catalog_category"
        verbose_name_plural = "categories"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Book(BaseModel):
    """
    Core book record (protocol sec. 7 - Book Upload Workflow).
    The actual file never gets exposed to clients directly - see BookAsset
    and the future `reader` app, which renders pages dynamically (sec. 9,
    Layer 3) rather than serving the underlying EPUB/PDF.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING = "pending", "Pending Approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        PUBLISHED = "published", "Published"

    class Language(models.TextChoices):
        ENGLISH = "en", "English"
        FRENCH = "fr", "French"
        KINYARWANDA = "rw", "Kinyarwanda"
        SWAHILI = "sw", "Swahili"

    author = models.ForeignKey(
        "accounts.AuthorProfile", on_delete=models.CASCADE, related_name="books"
    )
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, related_name="books"
    )

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    description = models.TextField(blank=True)
    keywords = models.CharField(max_length=500, blank=True, help_text="Comma-separated keywords")
    language = models.CharField(max_length=5, choices=Language.choices, default=Language.ENGLISH)
    isbn = models.CharField(max_length=20, blank=True)

    cover_image = models.ImageField(upload_to="covers/", blank=True, null=True)

    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="RWF")

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "catalog_book"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["language"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)[:280]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class BookAsset(BaseModel):
    """
    The encrypted source file behind a Book (sec. 9, Layer 1) plus envelope
    encryption metadata. In production `encrypted_file` would point at an
    AWS S3 key rather than local disk, but the encryption model is the
    same either way: the plaintext EPUB/PDF is never stored or served -
    only `reader.services` decrypts it, in memory, per page, per session.

    Envelope encryption: each book gets its own random data-encryption-key
    (DEK). The DEK itself is encrypted ("wrapped") with a master key that
    lives in settings/secrets manager, never in the database in the clear.
    """

    class FileType(models.TextChoices):
        EPUB = "epub", "EPUB"
        PDF = "pdf", "PDF"

    book = models.OneToOneField(Book, on_delete=models.CASCADE, related_name="asset")
    file_type = models.CharField(max_length=5, choices=FileType.choices)
    encrypted_file = models.FileField(upload_to="book_assets/")
    original_filename = models.CharField(max_length=255)
    checksum_sha256 = models.CharField(max_length=64, help_text="Checksum of the plaintext original")
    wrapped_key = models.TextField(help_text="Book's DEK, encrypted with the master key")
    page_count = models.PositiveIntegerField(null=True, blank=True)
    virus_scan_passed = models.BooleanField(default=False)

    class Meta:
        db_table = "catalog_book_asset"

    def __str__(self):
        return f"Asset for {self.book.title}"
