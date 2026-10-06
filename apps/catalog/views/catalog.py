from django.views.generic import DetailView, ListView

from ..filters import ProductFilter
from ..models import Category, Product


class CatalogView(ListView):
    model = Product
    template_name = 'catalog/catalog.html'
    context_object_name = 'products'
    paginate_by = 12

    def get_queryset(self):
        # Siempre público: solo activos y con categoría activa
        qs = Product.objects.filter(is_active=True, category__is_active=True).select_related('category')
        self.filter = ProductFilter(self.request.GET, queryset=qs)
        return self.filter.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.filter(is_active=True)
        context['current_category'] = self.request.GET.get('category', '')
        context['filter'] = getattr(self, 'filter', ProductFilter(self.request.GET, queryset=self.get_queryset()))
        # Para paginación genérica que preserve TODOS los parámetros
        query = self.request.GET.copy()
        query.pop('page', None)
        context['filter_query'] = query.urlencode()
        return context


class ProductDetailView(DetailView):
    model = Product
    template_name = 'catalog/product_detail.html'
    context_object_name = 'product'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        return Product.objects.filter(
            is_active=True,
            category__is_active=True,
        ).select_related('category')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['related_products'] = Product.objects.filter(
            category=self.object.category,
            is_active=True,
            category__is_active=True,
        ).exclude(pk=self.object.pk).select_related('category')[:4]
        return context
