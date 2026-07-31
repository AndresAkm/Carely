from ..models import *
# importar las serializaciones de los modelos
from ..serializer import *
# importar el módulo de ViewSets para las vistas de las API's
from rest_framework import viewsets


# Vistas para las APIs
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
