from decimal import Decimal

from django.conf import settings
from django.urls import reverse
from django.test import TestCase
from rest_framework.test import APITestCase

from apps.cart.models import Cart, CartItem
from apps.catalog.models import Category, Product
from apps.orders.models import Order, OrderItem
from apps.payments.models import Payment
from apps.users.models import User


class ResourceOwnershipTests(APITestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(username='a', email='a@example.com', password='pass12345')
        self.user_b = User.objects.create_user(username='b', email='b@example.com', password='pass12345')
        category = Category.objects.create(name='Test', icon='bi-test')
        product = Product.objects.create(category=category, name='Product', price=Decimal('10.00'))
        self.cart_b = Cart.objects.create(user=self.user_b)
        self.order_b = Order.objects.create(user=self.user_b)
        OrderItem.objects.create(order=self.order_b, product=product, quantity=1, unit_price=product.price)
        self.payment_b = Payment.objects.create(order=self.order_b, amount=Decimal('10.00'), payment_method='efectivo')

    def test_private_resources_require_authentication(self):
        for url in ('/api/v1/carrito/carritos/', '/api/v1/pedidos/pedidos/', '/api/v1/pagos/', '/api/v1/inventario/movimientos/'):
            self.assertIn(self.client.get(url).status_code, (401, 403))

    def test_user_cannot_access_other_users_resources(self):
        self.client.force_authenticate(self.user_a)
        self.assertEqual(self.client.get(f'/api/v1/carrito/carritos/{self.cart_b.pk}/').status_code, 404)
        self.assertEqual(self.client.get(f'/api/v1/pedidos/pedidos/{self.order_b.pk}/').status_code, 404)
        self.assertEqual(self.client.get(f'/api/v1/pagos/{self.payment_b.pk}/').status_code, 404)

    def test_user_api_is_admin_only(self):
        self.client.force_authenticate(self.user_a)
        response = self.client.get('/api/v1/usuarios/')
        self.assertEqual(response.status_code, 403)

    def test_logout_requires_post(self):
        self.client.force_authenticate(self.user_a)
        self.assertEqual(self.client.get('/accounts/logout/').status_code, 405)
        self.assertEqual(self.client.post('/accounts/logout/').status_code, 302)


class ProductDetailCartTests(TestCase):
    """El detalle de producto debe permitir comprar sin volver al catálogo."""

    def setUp(self):
        self.category = Category.objects.create(name='Cuidado facial', slug='cuidado-facial', icon='bi-test')
        self.product = Product.objects.create(
            category=self.category,
            name='Crema Hidratante',
            slug='crema-hidratante',
            price=Decimal('35000.00'),
            stock=10,
            is_active=True,
        )
        self.url = reverse('catalog:product_detail', args=[self.product.slug])

    def test_anonymous_sees_login_link_not_add_form(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('users:login'))
        self.assertNotContains(response, reverse('cart:add', args=[self.product.pk]))

    def test_authenticated_sees_add_to_cart_form(self):
        user = User.objects.create_user(username='u', email='u@example.com', password='pass12345')
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertContains(response, reverse('cart:add', args=[self.product.pk]))
        self.assertContains(response, 'name="quantity"')
        self.assertContains(response, 'csrfmiddlewaretoken')

    def test_out_of_stock_hides_form(self):
        self.product.stock = 0
        self.product.save(update_fields=['stock'])
        user = User.objects.create_user(username='u2', email='u2@example.com', password='pass12345')
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertNotContains(response, reverse('cart:add', args=[self.product.pk]))
        self.assertContains(response, 'Producto agotado')

    def test_add_to_cart_works_from_detail_page(self):
        user = User.objects.create_user(username='u3', email='u3@example.com', password='pass12345')
        self.client.force_login(user)
        self.client.post(
            reverse('cart:add', args=[self.product.pk]),
            {'quantity': 3},
            HTTP_REFERER=self.url,
        )
        cart = Cart.objects.get(user=user)
        item = cart.items.get(product=self.product)
        self.assertEqual(item.quantity, 3)


class FooterLinksTests(TestCase):
    """El footer se incluye en todas las páginas: no debe renderizar enlaces muertos."""

    def setUp(self):
        self.category = Category.objects.create(name='Perfumes', slug='perfumes', icon='bi-test')
        self.user = User.objects.create_user(username='u', email='u@example.com', password='pass12345')

    def test_categories_available_outside_catalog_views(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('cart:cart'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.category.name)
        self.assertContains(
            response, f'{reverse("catalog:home")}?category={self.category.slug}'
        )

    def test_categories_available_on_privacy_page(self):
        response = self.client.get(reverse('core:privacy'))
        self.assertContains(
            response, f'{reverse("catalog:home")}?category={self.category.slug}'
        )

    def test_no_dead_anchor_links(self):
        for url in (reverse('core:home'), reverse('catalog:home')):
            content = self.client.get(url).content.decode()
            self.assertNotIn('href="#"', content, f'href="#" encontrado en {url}')

    def test_contact_details_rendered(self):
        response = self.client.get(reverse('core:home'))
        self.assertContains(response, 'mailto:carelywebsite@gmail.com')
        self.assertContains(response, reverse('core:privacy'))


class PageRenderSmokeTests(TestCase):
    """Todas las páginas con footer deben renderizar sin errores de template."""

    def setUp(self):
        from apps.catalog.models import Product

        self.user = User.objects.create_user(username='u', email='u@example.com', password='pass12345')
        # Deshabilitar la cuenta exige 2FA activo; si no, la vista redirige.
        self.user.two_factor_enabled = True
        self.user.save()
        category = Category.objects.create(name='Perfumes', slug='perfumes', icon='bi-test')
        self.product = Product.objects.create(
            category=category, name='Aroma', slug='aroma',
            price=Decimal('50000.00'), stock=5, is_active=True,
        )
        self.cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=1)
        self.order = Order.objects.create(user=self.user)
        self.client.force_login(self.user)

    def test_public_pages_render(self):
        self.client.logout()
        urls = [
            reverse('core:home'),
            reverse('core:privacy'),
            reverse('catalog:home'),
            reverse('catalog:product_detail', args=[self.product.slug]),
            reverse('users:login'),
            reverse('users:register'),
            reverse('users:password_reset'),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_authenticated_pages_render(self):
        urls = [
            reverse('cart:cart'),
            reverse('orders:checkout'),
            reverse('orders:order_list'),
            reverse('orders:order_detail', args=[self.order.pk]),
            reverse('users:profile'),
            reverse('users:address_list'),
            reverse('users:address_create'),
            reverse('users:account_deactivate'),
            reverse('users:two_factor_setup'),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_extracted_stylesheets_are_linked(self):
        expectations = {
            reverse('cart:cart'): 'cart/css/cart.css',
            reverse('orders:checkout'): 'orders/css/checkout.css',
            reverse('orders:order_detail', args=[self.order.pk]): 'orders/css/order_detail.css',
        }
        for url, static_path in expectations.items():
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), static_path)


class DashboardSidebarTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin', email='admin@example.com', password='pass12345',
            role=User.Role.ADMIN, is_staff=True,
        )
        self.client.force_login(self.admin)

    def test_sidebar_has_no_dead_links(self):
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('href="#"', response.content.decode())


class OrderStatusFormTemplateTests(TestCase):
    """El JS del timeline depende del id que renderiza OrderStatusForm."""

    def setUp(self):
        from apps.orders.forms import OrderStatusForm

        self.form = OrderStatusForm()
        self.admin = User.objects.create_user(
            username='admin2', email='admin2@example.com', password='pass12345',
            role=User.Role.ADMIN, is_staff=True,
        )
        self.order = Order.objects.create(user=self.admin)
        self.url = reverse('dashboard:order_status', args=[self.order.pk])

    def test_notes_widget_uses_id_expected_by_javascript(self):
        self.assertEqual(self.form['notes'].id_for_label, 'id_order_notes')

    def test_status_update_page_references_existing_notes_id(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('id="id_order_notes"', content)
        self.assertIn("getElementById('id_order_notes')", content)


class ErrorPageTests(TestCase):
    """Las páginas de error deben renderizar con el estilo de Carely."""

    def test_404_view_returns_404_status(self):
        response = self.client.get(reverse('core:error_404'))
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, 'errors/404.html')

    def test_403_view_returns_403_status(self):
        response = self.client.get(reverse('core:error_403'))
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, 'errors/403.html')

    def test_unknown_url_renders_custom_404(self):
        response = self.client.get('/ruta-que-no-existe/')
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, 'errors/404.html')

    def test_404_shows_carely_content_not_django_default(self):
        content = self.client.get('/ruta-que-no-existe/').content.decode()
        self.assertIn('Esta página no existe', content)
        self.assertIn('carely-logo', content)
        # El mensaje por defecto de Django en inglés no debe aparecer.
        self.assertNotIn('Page not found', content)

    def test_404_offers_catalog_and_search(self):
        content = self.client.get(reverse('core:error_404')).content.decode()
        self.assertIn(reverse('catalog:home'), content)
        self.assertIn('name="q"', content)
        self.assertIn('Ver el catálogo', content)

    def test_403_offers_login_when_anonymous(self):
        content = self.client.get(reverse('core:error_403')).content.decode()
        self.assertIn(reverse('users:login'), content)
        self.assertIn('No tienes permiso', content)
        self.assertNotIn('Page not found', content)

    def test_403_offers_home_when_authenticated(self):
        user = User.objects.create_user(
            username='u', email='u@example.com', password='pass12345',
        )
        self.client.force_login(user)
        content = self.client.get(reverse('core:error_403')).content.decode()
        self.assertIn(reverse('core:home'), content)
        # Ya hay sesión: ofrecer "iniciar sesión" sería absurdo.
        self.assertNotIn(reverse('users:login'), content)

    def test_403_preserves_next_destination(self):
        response = self.client.get(reverse('core:error_403'), {'next': '/pedidos/'})
        self.assertEqual(response.context['next'], '/pedidos/')
        content = response.content.decode()
        self.assertIn(f'{reverse("users:login")}?next=/pedidos/', content)

    def test_403_falls_back_to_current_path(self):
        """Sin `next` explícito debe usar la ruta que se intentó abrir."""
        response = self.client.get(reverse('core:error_403'))
        self.assertEqual(response.context['next'], '/errores/403/')

    def test_403_uses_contact_email_from_settings(self):
        content = self.client.get(reverse('core:error_403')).content.decode()
        self.assertIn(settings.CARELY_EMAIL, content)

    def test_both_pages_load_carely_stylesheet(self):
        expectations = {
            reverse('core:error_404'): 404,
            reverse('core:error_403'): 403,
        }
        for url, status in expectations.items():
            with self.subTest(url=url):
                self.assertContains(
                    self.client.get(url), 'core/css/errors.css', status_code=status,
                )

    def test_error_pages_are_not_indexed(self):
        expectations = {
            reverse('core:error_404'): 404,
            reverse('core:error_403'): 403,
        }
        for url, status in expectations.items():
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), 'noindex', status_code=status)

    def test_real_403_from_protected_view_renders_carely_page(self):
        """El 403 de Django debe usar la plantilla de Carely, no la genérica."""
        user = User.objects.create_user(
            username='cliente', email='cliente@example.com', password='pass12345',
        )
        self.client.force_login(user)
        with self.settings(ROOT_URLCONF='apps.core.tests_test_urls'):
            response = self.client.get('/protegida/')
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, '403.html')
        self.assertContains(response, 'No tienes permiso', status_code=403)

    def test_real_404_from_raised_http404_renders_carely_page(self):
        """Igual para el 404: `Http404` debe pintar la página de Carely."""
        with self.settings(ROOT_URLCONF='apps.core.tests_test_urls'):
            response = self.client.get('/ruta-que-no-existe/')
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, '404.html')
        self.assertContains(response, 'Esta página no existe', status_code=404)

    def test_error_pages_are_reachable_in_development(self):
        """Con DEBUG=True Django no usa 404.html, así que las vistas existen."""
        with self.settings(DEBUG=True):
            self.assertEqual(self.client.get(reverse('core:error_404')).status_code, 404)
            self.assertEqual(self.client.get(reverse('core:error_403')).status_code, 403)


class ErrorPagesWithDebugMiddlewareTests(TestCase):
    """El middleware debe servir las páginas de Carely también con DEBUG=True."""

    def test_404_is_branded_with_debug_true(self):
        with self.settings(DEBUG=True):
            response = self.client.get('/esta-ruta-no-existe/')
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, 'Esta página no existe', status_code=404)
        self.assertNotContains(response, 'didn’t match any of these', status_code=404)

    def test_403_is_branded_with_debug_true(self):
        with self.settings(ROOT_URLCONF='apps.core.tests_test_urls', DEBUG=True):
            response = self.client.get('/protegida/')
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'No tienes permiso', status_code=403)
        self.assertNotContains(response, 'Username:', status_code=403)

    def test_api_paths_are_never_branded(self):
        """Bajo /api/ no se inyecta HTML: la API no debe recibir páginas web."""
        with self.settings(DEBUG=True):
            response = self.client.get(
                '/api/v1/no-existe/',
                headers={'accept': 'text/html'},
            )
        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, 'Esta página no existe', status_code=404)

    def test_json_client_response_is_passed_through_untouched(self):
        """Un cliente JSON no debe recibir nuestra página: dejamos pasar su respuesta.

        Nota: con `DEBUG=True` y una URL que no existe, Django entrega su propia
        página técnica HTML antes de que exista cualquier respuesta JSON. Este
        test comprueba lo que sí podemos garantizar: que el middleware no
        inyecta la plantilla de Carely cuando el cliente no pide HTML.
        """
        with self.settings(DEBUG=True):
            response = self.client.get(
                '/no-existe/',
                headers={'accept': 'application/json'},
            )
        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, 'Esta página no existe', status_code=404)

    def test_browser_gets_html_404(self):
        with self.settings(DEBUG=True):
            response = self.client.get(
                '/no-existe/',
                headers={'accept': 'text/html,application/xhtml+xml'},
            )
        self.assertIn('<html', response.content.decode().lower())

    def test_normal_pages_are_untouched(self):
        with self.settings(DEBUG=True):
            response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)

    def test_500_is_not_intercepted(self):
        """Los tracebacks de 500 deben seguir mostrándose en desarrollo."""
        self.client.raise_request_exception = False
        with self.settings(DEBUG=True, ROOT_URLCONF='apps.core.tests_test_urls'):
            # Django registra el traceback en el logger `django.request`;
            # lo silenciamos para no ensuciar la salida de los tests.
            with self.assertLogs('django.request', level='ERROR') as logs:
                response = self.client.get('/falla/')
        self.assertEqual(response.status_code, 500)
        self.assertTrue(
            any('Internal Server Error' in line for line in logs.output),
            logs.output,
        )
        self.assertNotContains(response, 'Esta página no existe', status_code=500)
        self.assertNotContains(response, 'No tienes permiso', status_code=500)

    def test_404_still_uses_carely_template_with_debug_false(self):
        with self.settings(DEBUG=False):
            response = self.client.get('/esta-ruta-no-existe/')
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, 'Esta página no existe', status_code=404)

    def test_error_pages_never_leak_url_patterns(self):
        with self.settings(DEBUG=True):
            content = self.client.get('/x/').content.decode()
        self.assertNotIn('URLconf defined in', content)
        self.assertNotIn('didn', content)