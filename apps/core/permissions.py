from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.users.models import User


def is_admin(user):
    return (
        user.is_authenticated
        and (user.is_staff or user.is_superuser or user.role == User.Role.ADMIN)
    )


class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return is_admin(request.user)


class IsAuthenticatedOrAdminReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.method in SAFE_METHODS or is_admin(request.user)
        )


class IsAdminOnly(BasePermission):
    def has_permission(self, request, view):
        return is_admin(request.user)


class IsAuthenticatedOwnedOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if is_admin(request.user):
            return True
        owner = getattr(obj, 'user', None)
        if owner is None and hasattr(obj, 'cart'):
            owner = obj.cart.user
        return owner == request.user

 
class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return is_admin(request.user)
