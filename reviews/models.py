from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from common.models import BaseModel


class Review(BaseModel):
    """
    Protocol sec. 3 (Reader: 'Leave reviews', Author: 'Respond to reviews').
    One review per reader per book, gated on actually owning it - see
    ReviewViewSet.perform_create, which checks LibraryEntry the same way
    reader.services does for reading sessions and bookmarks.
    """

    book = models.ForeignKey("catalog.Book", on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    author_response = models.TextField(blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "reviews_review"
        unique_together = ("book", "user")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} rated {self.book.title} {self.rating}/5"
