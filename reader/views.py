from django.http import HttpResponse
from rest_framework import permissions, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import LibraryEntry
from .models import Bookmark, Highlight
from .serializers import (
    StartSessionSerializer, ReadingSessionSerializer, BookmarkSerializer, HighlightSerializer,
)
from .services import start_session, render_page, _get_valid_session


def _client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _assert_owns_book(user, book):
    if not LibraryEntry.objects.filter(user=user, book=book).exists():
        raise PermissionDenied("You do not own this book.")


class StartReadingSessionView(APIView):
    """POST /api/v1/reader/sessions/ - open a reading session for an owned book."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = StartSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = start_session(
            user=request.user,
            book_id=serializer.validated_data["book_id"],
            device_id=serializer.validated_data.get("device_id"),
            ip_address=_client_ip(request),
        )
        return Response(ReadingSessionSerializer(session).data, status=201)


class ReadPageView(APIView):
    """
    GET /api/v1/reader/read/<token>/pages/<page_number>/
    Returns exactly one rendered, watermarked page as a PNG image - never
    the underlying file. See reader.services.render_page.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, token, page_number):
        session = _get_valid_session(token, _client_ip(request))
        if session.user != request.user:
            raise PermissionDenied("This session does not belong to you.")

        image_bytes = render_page(token, page_number, _client_ip(request))
        response = HttpResponse(image_bytes, content_type="image/png")
        response["Cache-Control"] = "no-store"  # never let a proxy/browser cache a page
        return response


class BookmarkViewSet(viewsets.ModelViewSet):
    """Reader's saved pages. Optionally filter with ?book=<id>."""

    serializer_class = BookmarkSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Bookmark.objects.filter(user=self.request.user)
        book_id = self.request.query_params.get("book")
        if book_id:
            qs = qs.filter(book_id=book_id)
        return qs

    def perform_create(self, serializer):
        _assert_owns_book(self.request.user, serializer.validated_data["book"])
        serializer.save(user=self.request.user)


class HighlightViewSet(viewsets.ModelViewSet):
    """Reader's highlighted passages + notes. Optionally filter with ?book=<id>."""

    serializer_class = HighlightSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Highlight.objects.filter(user=self.request.user)
        book_id = self.request.query_params.get("book")
        if book_id:
            qs = qs.filter(book_id=book_id)
        return qs

    def perform_create(self, serializer):
        _assert_owns_book(self.request.user, serializer.validated_data["book"])
        serializer.save(user=self.request.user)
