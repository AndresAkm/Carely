from rest_framework import viewsets

from ..models import *
# importar las serializaciones de los modelos
from ..serializer import *
# importar el módulo de ViewSets para las vistas de las API's
from apps.core.permissions import IsAdminOrReadOnly
from apps.core.permissions import is_admin


# Vistas para las APIs
class ProductViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    queryset = Product.objects.all()
    serializer_class = ProductSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset if is_admin(self.request.user) else queryset.filter(is_active=True)


class CategoryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset if is_admin(self.request.user) else queryset.filter(is_active=True)
