from django.utils import timezone
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from orders.models import LibraryEntry
from .models import Review
from .serializers import ReviewSerializer, AuthorResponseSerializer


class ReviewViewSet(viewsets.ModelViewSet):
    """Public read; write requires ownership. Filter with ?book=<id>."""

    serializer_class = ReviewSerializer

    def get_queryset(self):
        qs = Review.objects.select_related("user", "book")
        book_id = self.request.query_params.get("book")
        if book_id:
            qs = qs.filter(book_id=book_id)
        return qs

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        book = serializer.validated_data["book"]
        if not LibraryEntry.objects.filter(user=self.request.user, book=book).exists():
            raise PermissionDenied("You can only review books you own.")
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        review = self.get_object()
        if review.user != self.request.user:
            raise PermissionDenied("You can only edit your own review.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.user != self.request.user:
            raise PermissionDenied("You can only delete your own review.")
        instance.delete()

    @action(detail=True, methods=["post"])
    def respond(self, request, pk=None):
        """The book's author replies to a review (protocol sec. 12)."""
        review = self.get_object()
        if review.book.author.user != request.user:
            raise PermissionDenied("Only the book's author can respond to this review.")
        serializer = AuthorResponseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review.author_response = serializer.validated_data["author_response"]
        review.responded_at = timezone.now()
        review.save(update_fields=["author_response", "responded_at"])

        from notifications.services import notify
        from notifications.models import Notification
        notify(
            review.user,
            Notification.Kind.REVIEW_RECEIVED,
            f"The author replied to your review of '{review.book.title}'.",
            link=f"/books/{review.book.id}",
        )
        return Response(ReviewSerializer(review).data)
