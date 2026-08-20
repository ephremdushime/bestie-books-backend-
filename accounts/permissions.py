from rest_framework.permissions import BasePermission


class IsAdminRole(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.role == request.user.Role.ADMIN or request.user.is_staff)
        )


class IsAuthorRole(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == request.user.Role.AUTHOR
        )


class IsSelfOrAdmin(BasePermission):
    """Object-level: only the owning user or an admin may access."""

    def has_object_permission(self, request, view, obj):
        owner = getattr(obj, "user", obj)
        return owner == request.user or request.user.role == request.user.Role.ADMIN
