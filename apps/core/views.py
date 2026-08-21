from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from django.views.generic import TemplateView

from apps.catalog.models import Category, Product
from apps.core.permissions import is_admin
from apps.orders.models import Order

User = get_user_model()


class LandingView(TemplateView):
    template_name = 'core/home.html'

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
                'icon': 'bi-award',
                'title': 'Compromiso con la Calidad',
                'description': 'Nos asociamos con marcas que comparten nuestro compromiso con la calidad y la sostenibilidad.',
            },
        ]
        context['categories'] = Category.objects.filter(is_active=True)
        context['featured_products'] = Product.objects.filter(
            is_active=True, featured=True
        ).select_related('category')[:6]
        return context


class DashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'core/dashboard.html'

    def test_func(self):
        return is_admin(self.request.user)

    def handle_no_permission(self):
        return redirect('catalog:home')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_users'] = User.objects.count()
        context['total_products'] = Product.objects.count()
        context['total_categories'] = Category.objects.count()
        context['total_orders'] = Order.objects.count()

        context['recent_users'] = User.objects.order_by('-date_joined')[:5]
        context['recent_orders'] = Order.objects.select_related('user')[:5]
        return context
