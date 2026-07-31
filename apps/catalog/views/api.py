from rest_framework import viewsets

from ..models import *
# importar las serializaciones de los modelos
from ..serializer import *
# importar el módulo de ViewSets para las vistas de las API's
from apps.core.permissions import IsAdminOrReadOnly


# Vistas para las APIs
class ProductViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    queryset = Product.objects.all()
    serializer_class = ProductSerializer


class CategoryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    queryset = Category.objects.all()
    serializer_class = CategorySerializer