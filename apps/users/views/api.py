from rest_framework import viewsets

from rest_framework_simplejwt.views import TokenObtainPairView

from ..models import User
from ..serializer import UserSerializer
from apps.core.permissions import IsAdmin


# Vistas para las APIs
class UserViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdmin]
    queryset = User.objects.all()
    serializer_class = UserSerializer
    http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']

    def get_queryset(self):
        if self.request.user.is_superuser or self.request.user.is_staff or getattr(self.request.user, 'role', None) == User.Role.ADMIN:
            return super().get_queryset()
        return User.objects.filter(pk=self.request.user.pk)
