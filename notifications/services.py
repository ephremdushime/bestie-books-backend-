from .models import Notification


def notify(user, kind: str, message: str, link: str = "") -> Notification:
    """Single call site for creating a notification - every trigger point
    in the app (payments, catalog approvals, payouts) goes through this."""
    return Notification.objects.create(user=user, kind=kind, message=message, link=link)
