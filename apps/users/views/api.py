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
