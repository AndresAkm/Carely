import django_filters
from django.db.models import Q

from .models import Product, Category


class ProductFilter(django_filters.FilterSet):
    # Búsqueda libre: nombre o descripción
    q = django_filters.CharFilter(method='filter_search', label='Buscar')

    # Rango de precio
    min_price = django_filters.NumberFilter(field_name='price', lookup_expr='gte', label='Precio mínimo')
    max_price = django_filters.NumberFilter(field_name='price', lookup_expr='lte', label='Precio máximo')

    # Filtros booleanos/relacionales
    category = django_filters.ModelChoiceFilter(
        field_name='category',
        queryset=Category.objects.filter(is_active=True),
        to_field_name='slug',
        label='Categoría',
    )
    brand = django_filters.CharFilter(lookup_expr='iexact', label='Marca')
    featured = django_filters.BooleanFilter(label='Destacado')
    has_discount = django_filters.BooleanFilter(method='filter_has_discount', label='Con descuento')
    min_discount = django_filters.NumberFilter(field_name='discount_percent', lookup_expr='gte', label='Descuento mínimo (%)')
    max_discount = django_filters.NumberFilter(field_name='discount_percent', lookup_expr='lte', label='Descuento máximo (%)')
    in_stock = django_filters.BooleanFilter(method='filter_in_stock', label='Solo en stock')

    # Orden configurable
    ordering = django_filters.OrderingFilter(
        fields=(
            ('price', 'price'),
            ('name', 'name'),
            ('created_at', 'created_at'),
        ),
        field_labels={
            'price': 'Precio',
            'name': 'Nombre',
            'created_at': 'Fecha',
        },
        label='Ordenar por',
    )

    class Meta:
        model = Product
        fields = ['category', 'brand', 'featured', 'is_active']

    def filter_search(self, queryset, name, value):
        if not value or not value.strip():
            return queryset
        return queryset.filter(Q(name__icontains=value) | Q(description__icontains=value))

    def filter_has_discount(self, queryset, name, value):
        if value:
            return queryset.filter(discount_percent__gt=0)
        return queryset

    def filter_in_stock(self, queryset, name, value):
        if value:
            return queryset.filter(stock__gt=0)
        return queryset