from rest_framework import viewsets

from accounts.permissions import IsAdminRole
from .models import Coupon
from .serializers import CouponSerializer


class CouponViewSet(viewsets.ModelViewSet):
    """Admin-only management of discount codes."""

    queryset = Coupon.objects.all()
    serializer_class = CouponSerializer
    permission_classes = [IsAdminRole]
