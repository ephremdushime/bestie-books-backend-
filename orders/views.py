from rest_framework import viewsets, permissions, mixins
from rest_framework.response import Response

from .models import Order, LibraryEntry
from .serializers import OrderSerializer, CreateOrderSerializer, LibraryEntrySerializer


class OrderViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                    mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    Readers create an Order from a set of book IDs, then hand the Order ID
    to POST /api/v1/payments/ to actually pay for it (see payments app).
    """

    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related("items")

    def get_serializer_class(self):
        if self.action == "create":
            return CreateOrderSerializer
        return OrderSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response(OrderSerializer(order).data, status=201)


class LibraryViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """A reader's personal library - the books they actually own access to."""

    serializer_class = LibraryEntrySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return LibraryEntry.objects.filter(user=self.request.user).select_related("book")
