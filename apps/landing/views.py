from django.views.generic import TemplateView, ListView
from apps.core.models import Category, Product


class LandingView(TemplateView):
    template_name = 'landing/landing.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['benefits'] = [
            {
                'icon': 'bi-shield-check',
                'title': 'Productos 100% Originales',
                'description': 'Trabajamos directamente con marcas reconocidas para garantizar la autenticidad de cada producto.',
            },
            {
                'icon': 'bi-truck',
                'title': 'Envío Rápido y Seguro',
                'description': 'Recibe tus productos en la puerta de tu casa con entregas rápidas y empaque cuidadoso.',
            },
            {
                'icon': 'bi-star',
                'title': 'Asesoría Personalizada',
                'description': 'Nuestro equipo de expertos te ayuda a encontrar los productos ideales para tu tipo de piel.',
            },
            {
                'icon': 'bi-arrow-repeat',
                'title': 'Devoluciones Sin Complicaciones',
                'description': 'Si no estás satisfecha, puedes devolver tu producto en un plazo de 30 días.',
            },
        ]
        context['why_us'] = [
            {
                'icon': 'bi-heart',
                'title': 'Cuidado de tu Piel',
                'description': 'Seleccionamos cuidadosamente cada producto para ofrecerte lo mejor para el cuidado de tu piel.',
            },
            {
                'icon': 'bi-emoji-smile',
                'title': 'Experiencia de Compra',
                'description': 'Disfruta de una experiencia de compra diseñada pensando en ti, desde la navegación hasta la entrega.',
            },
            {
                'icon': 'bi-leaf',
                'title': 'Compromiso con la Calidad',
                'description': 'Nos asociamos con marcas que comparten nuestro compromiso con la calidad y la sostenibilidad.',
            },
        ]
        context['categories'] = Category.objects.filter(is_active=True)
        context['featured_products'] = Product.objects.filter(
            is_active=True, featured=True
        ).select_related('category')[:6]
        return context


class CatalogView(ListView):
    model = Product
    template_name = 'landing/catalog.html'
    context_object_name = 'products'
    paginate_by = 12

    def get_queryset(self):
        qs = Product.objects.filter(is_active=True).select_related('category')
        category_slug = self.request.GET.get('category')
        if category_slug:
            qs = qs.filter(category__slug=category_slug)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.filter(is_active=True)
        context['current_category'] = self.request.GET.get('category', '')
        return context
