import secrets

from django.conf import settings
from django.db import models

from common.models import BaseModel


def _generate_token() -> str:
    return secrets.token_urlsafe(32)


class ReadingSession(BaseModel):
    """
    Protocol sec. 9, Layer 2: every reading session gets a unique encrypted
    access token. The page-rendering endpoint requires a valid, unexpired,
    non-revoked session token - it never accepts a raw book/file reference
    on its own.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reading_sessions")
    book = models.ForeignKey("catalog.Book", on_delete=models.CASCADE, related_name="reading_sessions")
    device = models.ForeignKey("accounts.Device", on_delete=models.SET_NULL, null=True, blank=True)

    token = models.CharField(max_length=64, unique=True, default=_generate_token)
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    last_ip = models.GenericIPAddressField(null=True, blank=True)
    is_revoked = models.BooleanField(default=False)
    revoked_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "reader_reading_session"
        indexes = [models.Index(fields=["token"])]

    def __str__(self):
        return f"Session for {self.user.email} / {self.book.title}"


class PageAccessLog(BaseModel):
    """
    Protocol sec. 9, Layer 7 (session monitoring): records each page
    request so suspicious patterns - multiple IPs, rapid switching -
    can be detected and the session auto-revoked.
    """

    session = models.ForeignKey(ReadingSession, on_delete=models.CASCADE, related_name="access_logs")
    page_number = models.PositiveIntegerField()
    ip_address = models.GenericIPAddressField()
    accessed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reader_page_access_log"
        ordering = ["-accessed_at"]


class Bookmark(BaseModel):
    """A reader's saved page (protocol sec. 3 - Reader: 'Bookmark pages')."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookmarks")
    book = models.ForeignKey("catalog.Book", on_delete=models.CASCADE, related_name="bookmarks")
    page_number = models.PositiveIntegerField()
    label = models.CharField(max_length=150, blank=True)

    class Meta:
        db_table = "reader_bookmark"
        unique_together = ("user", "book", "page_number")
        ordering = ["page_number"]

    def __str__(self):
        return f"{self.user.email} - {self.book.title} p.{self.page_number}"


class Highlight(BaseModel):
    """
    A reader's highlighted passage + optional note (protocol sec. 3 -
    Reader: 'Highlight text'). Storing the excerpt text itself (not just
    coordinates) keeps this simple across both PDF and reflowed EPUB
    pages, where the same text can land at different on-page positions.
    """

    class Color(models.TextChoices):
        YELLOW = "yellow", "Yellow"
        GREEN = "green", "Green"
        BLUE = "blue", "Blue"
        PINK = "pink", "Pink"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="highlights")
    book = models.ForeignKey("catalog.Book", on_delete=models.CASCADE, related_name="highlights")
    page_number = models.PositiveIntegerField()
    excerpt_text = models.TextField()
    note = models.TextField(blank=True)
    color = models.CharField(max_length=10, choices=Color.choices, default=Color.YELLOW)

    class Meta:
        db_table = "reader_highlight"
        ordering = ["page_number", "created_at"]

    def __str__(self):
        return f"{self.user.email} - {self.book.title} p.{self.page_number}"
