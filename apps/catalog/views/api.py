from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend

from ..filters import ProductFilter
from ..models import *
# importar las serializaciones de los modelos
from ..serializer import *
# importar el módulo de ViewSets para las vistas de las API's
from apps.core.permissions import IsAdminOrReadOnly
from apps.core.permissions import is_admin


class ProductPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 100


# Vistas para las APIs
class ProductViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    queryset = Product.objects.all().select_related('category')
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = ProductFilter
    pagination_class = ProductPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        # Admin ve todo; lectura pública solo activos + categoría activa
        if is_admin(self.request.user):
            return queryset
        return queryset.filter(is_active=True, category__is_active=True)


class CategoryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset if is_admin(self.request.user) else queryset.filter(is_active=True)
