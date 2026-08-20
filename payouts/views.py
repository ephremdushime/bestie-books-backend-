from django.utils import timezone
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from accounts.permissions import IsAdminRole, IsAuthorRole
from .models import PayoutRequest
from .serializers import PayoutRequestSerializer
from .services import available_balance


class PayoutRequestViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                            mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = PayoutRequestSerializer

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthorRole()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if user.role == user.Role.ADMIN or user.is_staff:
            return PayoutRequest.objects.all()
        return PayoutRequest.objects.filter(author__user=user)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthorRole])
    def balance(self, request):
        profile = getattr(request.user, "author_profile", None)
        if profile is None:
            return Response({"detail": "No author profile."}, status=404)
        return Response({"available_balance": available_balance(profile)})

    @action(detail=True, methods=["post"], permission_classes=[IsAdminRole])
    def approve(self, request, pk=None):
        payout = self.get_object()
        payout.status = PayoutRequest.Status.APPROVED
        payout.save(update_fields=["status"])
        self._notify(payout, "Your payout request was approved.")
        return Response(PayoutRequestSerializer(payout).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminRole])
    def mark_paid(self, request, pk=None):
        payout = self.get_object()
        payout.status = PayoutRequest.Status.PAID
        payout.processed_at = timezone.now()
        payout.save(update_fields=["status", "processed_at"])
        self._notify(payout, f"Your payout of {payout.amount} {payout.currency} has been paid out.")
        return Response(PayoutRequestSerializer(payout).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminRole])
    def reject(self, request, pk=None):
        payout = self.get_object()
        payout.status = PayoutRequest.Status.REJECTED
        payout.note = request.data.get("note", "")
        payout.processed_at = timezone.now()
        payout.save(update_fields=["status", "note", "processed_at"])
        self._notify(payout, "Your payout request was declined. See the note on your dashboard.")
        return Response(PayoutRequestSerializer(payout).data)

    def _notify(self, payout, message):
        from notifications.services import notify
        from notifications.models import Notification
        notify(payout.author.user, Notification.Kind.PAYOUT_UPDATE, message, link="/dashboard")
