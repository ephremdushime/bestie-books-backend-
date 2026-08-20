from django.utils import timezone
from rest_framework import viewsets, permissions, parsers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from accounts.permissions import IsAdminRole, IsAuthorRole
from .models import Category, Book, BookAsset
from .serializers import (
    CategorySerializer, BookListSerializer, BookDetailSerializer, BookWriteSerializer,
    BookAssetSerializer,
)
from .services import ingest_book_file


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsAdminRole()]
        return [permissions.AllowAny()]


class BookViewSet(viewsets.ModelViewSet):
    """
    - Anonymous / reader users: see only PUBLISHED books.
    - Authors: also see their own books in any status.
    - Admins: see everything, plus can approve/reject/publish.
    """

    def get_queryset(self):
        user = self.request.user
        qs = Book.objects.select_related("author", "category")
        if user.is_authenticated and user.role == user.Role.ADMIN:
            return qs
        if user.is_authenticated and user.role == user.Role.AUTHOR:
            return qs.filter(author__user=user) | qs.filter(status=Book.Status.PUBLISHED)
        return qs.filter(status=Book.Status.PUBLISHED)

    def get_serializer_class(self):
        if self.action == "list":
            return BookListSerializer
        if self.action in ("create", "update", "partial_update"):
            return BookWriteSerializer
        return BookDetailSerializer

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy",
                            "submit_for_approval", "upload_asset"):
            return [IsAuthorRole()]
        if self.action in ("approve", "reject"):
            return [IsAdminRole()]
        return [permissions.AllowAny()]

    def perform_create(self, serializer):
        author_profile = getattr(self.request.user, "author_profile", None)
        if author_profile is None:
            raise PermissionDenied("Only users with an author profile can upload books.")
        serializer.save(author=author_profile, status=Book.Status.DRAFT)

    def perform_update(self, serializer):
        book = self.get_object()
        if book.author.user != self.request.user:
            raise PermissionDenied("You can only edit your own books.")
        serializer.save()

    @action(detail=True, methods=["post"])
    def submit_for_approval(self, request, pk=None):
        book = self.get_object()
        if book.author.user != request.user:
            raise PermissionDenied("You can only submit your own books.")
        book.status = Book.Status.PENDING
        book.save(update_fields=["status"])
        return Response({"status": book.status})

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        book = self.get_object()
        book.status = Book.Status.PUBLISHED
        book.published_at = timezone.now()
        book.save(update_fields=["status", "published_at"])

        from notifications.services import notify
        from notifications.models import Notification
        notify(
            book.author.user,
            Notification.Kind.BOOK_APPROVED,
            f"'{book.title}' was approved and is now live.",
            link=f"/books/{book.id}",
        )
        return Response({"status": book.status, "published_at": book.published_at})

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        book = self.get_object()
        book.status = Book.Status.REJECTED
        book.save(update_fields=["status"])

        from notifications.services import notify
        from notifications.models import Notification
        notify(
            book.author.user,
            Notification.Kind.BOOK_REJECTED,
            f"'{book.title}' was not approved. Check with the Bestie Books team for details.",
            link="/dashboard",
        )
        return Response({"status": book.status})

    @action(detail=True, methods=["post"], parser_classes=[parsers.MultiPartParser])
    def upload_asset(self, request, pk=None):
        """
        Author uploads the EPUB/PDF for their book. The file is encrypted
        (sec. 9, Layer 1) before it ever touches disk - see
        catalog.services.ingest_book_file - and the response never echoes
        back anything that would let a client reconstruct the plaintext.
        """
        book = self.get_object()
        if book.author.user != request.user:
            raise PermissionDenied("You can only upload files for your own books.")

        uploaded_file = request.FILES.get("file")
        file_type = request.data.get("file_type")
        if not uploaded_file or file_type not in BookAsset.FileType.values:
            raise ValidationError("Provide 'file' and 'file_type' (epub or pdf).")

        asset = ingest_book_file(book, uploaded_file, file_type)
        return Response(BookAssetSerializer(asset).data, status=201)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthorRole])
    def my_sales(self, request):
        """
        Per-book sales summary for the Author Dashboard (protocol sec. 12).
        units_sold counts LibraryEntry rows - created only after a payment
        actually confirms (see payments.services.confirm_payment) - so
        this can never overcount a book as sold before it's truly paid for.
        """
        from django.db.models import Count, Sum
        from orders.models import LibraryEntry

        author_profile = getattr(request.user, "author_profile", None)
        if author_profile is None:
            raise PermissionDenied("No author profile for this account.")

        books = Book.objects.filter(author=author_profile)
        sales_by_book = {
            row["book"]: row
            for row in LibraryEntry.objects.filter(book__in=books)
            .values("book")
            .annotate(units_sold=Count("id"), revenue=Sum("order_item__unit_price"))
        }

        data = []
        for book in books:
            sales = sales_by_book.get(book.id, {})
            data.append({
                "id": str(book.id),
                "title": book.title,
                "status": book.status,
                "price": str(book.price),
                "currency": book.currency,
                "units_sold": sales.get("units_sold", 0),
                "revenue": str(sales.get("revenue") or 0),
            })
        return Response(data)
