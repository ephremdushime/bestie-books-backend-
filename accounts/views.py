from rest_framework import generics, viewsets, permissions
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import User, Device
from .serializers import RegisterSerializer, UserSerializer, DeviceSerializer, AuthorProfileSerializer

MAX_ACTIVE_DEVICES = 2  # protocol sec. 9, Layer 6


class RegisterView(generics.CreateAPIView):
    """Public sign-up endpoint (protocol sec. 5). Issues no tokens itself -
    the client should follow up with /api/v1/auth/token/ to log in."""

    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class MeView(APIView):
    """Get/update the authenticated user's own profile."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class AuthorMeView(APIView):
    """The author dashboard's entry point: the current user's AuthorProfile."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        profile = getattr(request.user, "author_profile", None)
        if profile is None:
            return Response({"detail": "No author profile for this account."}, status=404)
        return Response(AuthorProfileSerializer(profile).data)

    def patch(self, request):
        profile = getattr(request.user, "author_profile", None)
        if profile is None:
            return Response({"detail": "No author profile for this account."}, status=404)
        serializer = AuthorProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class DeviceViewSet(viewsets.ModelViewSet):
    """
    A reader's registered devices. Enforces the 2-device cap from the
    protocol; a request that would exceed it is rejected with guidance
    to deactivate an existing device or go through verification instead
    (the verification flow itself belongs to a future `security` app).
    """

    serializer_class = DeviceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Device.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        active_count = Device.objects.filter(user=self.request.user, is_active=True).count()
        if active_count >= MAX_ACTIVE_DEVICES:
            raise ValidationError(
                "Maximum of 2 active devices reached. Deactivate an existing "
                "device or complete additional-device verification first."
            )
        serializer.save(user=self.request.user)
