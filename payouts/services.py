from django.db.models import Sum

from orders.models import LibraryEntry
from .models import PayoutRequest


def available_balance(author_profile) -> float:
    """
    Total confirmed revenue for this author's books, minus anything
    already requested/approved/paid (rejected payouts free the balance
    back up). Uses the same LibraryEntry-based accounting as
    catalog.BookViewSet.my_sales, so the two numbers can never disagree.
    """
    from catalog.models import Book

    books = Book.objects.filter(author=author_profile)
    total_revenue = (
        LibraryEntry.objects.filter(book__in=books)
        .aggregate(total=Sum("order_item__unit_price"))["total"]
        or 0
    )
    already_claimed = (
        PayoutRequest.objects.filter(author=author_profile)
        .exclude(status=PayoutRequest.Status.REJECTED)
        .aggregate(total=Sum("amount"))["total"]
        or 0
    )
    return float(total_revenue) - float(already_claimed)
