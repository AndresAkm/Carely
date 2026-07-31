from rest_framework import viewsets

from ..models import *
# importar las serializaciones de los modelos
from ..serializer import *
# importar el módulo de ViewSets para las vistas de las API's
from apps.core.permissions import IsAdmin


# Vistas para las APIs
class UserViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdmin]
    queryset = User.objects.all()
    serializer_class = UserSerializer
