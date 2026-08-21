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

 
class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return is_admin(request.user)
