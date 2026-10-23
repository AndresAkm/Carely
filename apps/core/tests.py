import re
from decimal import Decimal
from unittest.mock import patch

from django.conf import settings
from django.templatetags.static import static
from django.urls import reverse
from django.test import TestCase
from rest_framework.test import APITestCase

from apps.cart.models import Cart, CartItem
from apps.catalog.models import Category, Product
from apps.orders.models import Order, OrderItem
from apps.payments.models import Payment
from apps.users.models import Address, City, Department, User
from apps.users.services import GmailServiceError
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.core.forms import SiteCustomizationForm
from apps.core.landing import DEFAULT_BENEFITS
from apps.core.models import ContactRequest, LandingBenefit, SiteCustomization, validate_plain_text


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
            # El enlace de contacto abre un modal (data-bs-toggle), no es un
            # ancla muerta. El resto de `href="#"` sí serían enlaces rotos.
            without_modal_triggers = re.sub(
                r'<a\b[^>]*data-bs-toggle="modal"[^>]*>', '<a>', content
            )
            self.assertNotIn('href="#"', without_modal_triggers, f'href="#" encontrado en {url}')

    def test_contact_details_rendered(self):
        response = self.client.get(reverse('core:home'))
        self.assertContains(response, 'mailto:carelywebsite@gmail.com')
        self.assertContains(response, reverse('core:privacy'))

    def test_contact_link_opens_the_modal(self):
        response = self.client.get(reverse('core:home'))
        self.assertContains(response, 'data-bs-target="#contactModal"')
        self.assertContains(response, 'data-contact-form')
        self.assertContains(response, reverse('core:contact'))


class ContactFormTests(TestCase):
    """El formulario del modal de contacto envía el mensaje por correo."""

    def setUp(self):
        self.url = reverse('core:contact')

    def _post(self, **overrides):
        data = {
            'name': 'Ana Restrepo',
            'email': 'ana@example.com',
            'subject': 'Una duda sobre el envío',
            'message': 'Hola, quiero saber si hacen envíos a mi ciudad.',
        }
        data.update(overrides)
        return self.client.post(self.url, data)

    def test_valid_submission_notifies_team_and_sender(self):
        with patch('apps.core.services.GmailService.send_message', return_value=True) as send:
            response = self._post()
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(send.call_count, 2)
        self.assertEqual(send.call_args_list[0].kwargs['recipient'], settings.CARELY_EMAIL)
        self.assertEqual(send.call_args_list[1].kwargs['recipient'], 'ana@example.com')

    def test_invalid_form_returns_field_errors(self):
        response = self._post(name='', email='no-es-un-correo', message='corto')
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['ok'])
        self.assertIn('name', data['errors'])
        self.assertIn('email', data['errors'])
        self.assertIn('message', data['errors'])

    def test_email_failure_returns_502(self):
        with patch(
            'apps.core.services.GmailService.send_message',
            side_effect=GmailServiceError('sin red'),
        ):
            response = self._post()
        self.assertEqual(response.status_code, 502)
        self.assertFalse(response.json()['ok'])
        self.assertIn('message', response.json())


class ContactRequestPanelTests(TestCase):
    """Las solicitudes del modal de contacto se atienden desde el panel."""

    def setUp(self):
        self.contact_url = reverse('core:contact')
        self.admin = User.objects.create_user(
            username='soporte@carely.test', email='soporte@carely.test',
            password='pass12345', role=User.Role.ADMIN, is_staff=True,
            first_name='Sofía', last_name='Soporte',
        )
        self.cliente = User.objects.create_user(
            username='cliente-solicitudes@carely.test',
            email='cliente-solicitudes@carely.test',
            password='pass12345',
        )
        self.lista_url = reverse('dashboard:contact_request_list')

    def crear_solicitud(self, **overrides):
        data = {
            'name': 'Ana Restrepo',
            'email': 'ana@example.com',
            'subject': 'Una duda sobre el envío',
            'message': 'Hola, quiero saber si hacen envíos a mi ciudad.',
        }
        data.update(overrides)
        return ContactRequest.objects.create(**data)

    def detalle_url(self, contact_request):
        return reverse('dashboard:contact_request_detail', args=[contact_request.pk])

    def test_valid_submission_is_saved_for_the_panel(self):
        with patch('apps.core.services.GmailService.send_message', return_value=True):
            response = self.client.post(self.contact_url, {
                'name': 'Ana Restrepo',
                'email': 'ana@example.com',
                'subject': 'Una duda sobre el envío',
                'message': 'Hola, quiero saber si hacen envíos a mi ciudad.',
            })
        self.assertEqual(response.status_code, 200)
        contact_request = ContactRequest.objects.get()
        self.assertEqual(contact_request.email, 'ana@example.com')
        self.assertEqual(contact_request.status, ContactRequest.Status.PENDIENTE)

    def test_email_failure_keeps_the_saved_request(self):
        with patch(
            'apps.core.services.GmailService.send_message',
            side_effect=GmailServiceError('sin red'),
        ):
            response = self.client.post(self.contact_url, {
                'name': 'Ana Restrepo',
                'email': 'ana@example.com',
                'subject': 'Una duda',
                'message': 'Quiero saber si tienen envíos a mi ciudad.',
            })
        self.assertEqual(response.status_code, 502)
        self.assertTrue(ContactRequest.objects.filter(email='ana@example.com').exists())

    def test_admin_sees_the_request_in_the_list(self):
        self.crear_solicitud()
        self.client.force_login(self.admin)
        response = self.client.get(self.lista_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ana Restrepo')
        self.assertContains(response, 'ana@example.com')
        self.assertContains(response, 'Pendiente')

    def test_filter_by_status(self):
        pendiente = self.crear_solicitud()
        self.crear_solicitud(name='Beatriz', status=ContactRequest.Status.RESPONDIDA)
        self.client.force_login(self.admin)
        response = self.client.get(self.lista_url, {'status': ContactRequest.Status.RESPONDIDA})
        self.assertContains(response, 'Beatriz')
        self.assertNotContains(response, pendiente.name)

    def test_client_cannot_access_the_panel(self):
        contact_request = self.crear_solicitud()
        self.client.force_login(self.cliente)
        for url in (self.lista_url, self.detalle_url(contact_request)):
            with self.subTest(url=url):
                self.assertRedirects(self.client.get(url), reverse('core:home'))

    def test_anonymous_cannot_access_the_panel(self):
        contact_request = self.crear_solicitud()
        self.assertEqual(self.client.get(self.lista_url).status_code, 302)
        self.assertEqual(self.client.get(self.detalle_url(contact_request)).status_code, 302)

    def test_admin_reply_is_sent_and_request_marked_answered(self):
        contact_request = self.crear_solicitud()
        self.client.force_login(self.admin)
        reply = 'Hola Ana, sí hacemos envíos a tu ciudad. Quedamos atentos.'
        with patch('apps.core.services.GmailService.send_message', return_value=True) as send:
            response = self.client.post(self.detalle_url(contact_request), {'reply': reply})

        self.assertRedirects(response, self.detalle_url(contact_request))
        contact_request.refresh_from_db()
        self.assertEqual(contact_request.status, ContactRequest.Status.RESPONDIDA)
        self.assertEqual(contact_request.reply, reply)
        self.assertEqual(contact_request.replied_by, self.admin)
        self.assertIsNotNone(contact_request.replied_at)

        kwargs = send.call_args.kwargs
        self.assertEqual(kwargs['recipient'], 'ana@example.com')
        self.assertEqual(kwargs['reply_to'], [self.admin.email])

    def test_empty_reply_is_rejected(self):
        contact_request = self.crear_solicitud()
        self.client.force_login(self.admin)
        with patch('apps.core.services.GmailService.send_message', return_value=True) as send:
            response = self.client.post(self.detalle_url(contact_request), {'reply': '   '})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Escribe una respuesta antes de enviarla.')
        self.assertEqual(send.call_count, 0)
        contact_request.refresh_from_db()
        self.assertEqual(contact_request.status, ContactRequest.Status.PENDIENTE)

    def test_email_failure_keeps_the_request_pending(self):
        contact_request = self.crear_solicitud()
        self.client.force_login(self.admin)
        with patch(
            'apps.core.services.GmailService.send_message',
            side_effect=GmailServiceError('sin red'),
        ):
            response = self.client.post(
                self.detalle_url(contact_request),
                {'reply': 'Una respuesta que no salió.'},
                follow=True,
            )
        self.assertContains(response, 'No pudimos enviar la respuesta')
        contact_request.refresh_from_db()
        self.assertEqual(contact_request.status, ContactRequest.Status.PENDIENTE)
        self.assertEqual(contact_request.reply, '')
        self.assertIsNone(contact_request.replied_by)


class MyContactRequestsTests(TestCase):
    """Cada cliente ve sus propias solicitudes y la respuesta cuando existe."""

    def setUp(self):
        self.cliente = User.objects.create_user(
            username='cliente-panel@carely.test',
            email='cliente-panel@carely.test',
            password='pass12345',
            first_name='Laura',
            last_name='Cliente',
        )
        self.otro = User.objects.create_user(
            username='otro-panel@carely.test',
            email='otro-panel@carely.test',
            password='pass12345',
        )
        self.lista_url = reverse('users:contact_request_list')

    def crear_solicitud(self, **overrides):
        data = {
            'name': 'Laura Cliente',
            'email': self.cliente.email,
            'subject': 'Duda con mi pedido',
            'message': 'Quisiera saber cuándo llega mi pedido.',
        }
        data.update(overrides)
        return ContactRequest.objects.create(**data)

    def detalle_url(self, contact_request):
        return reverse('users:contact_request_detail', args=[contact_request.pk])

    def test_anonymous_is_redirected_to_login(self):
        contact_request = self.crear_solicitud()
        login_url = reverse('users:login')
        for url in (self.lista_url, self.detalle_url(contact_request)):
            with self.subTest(url=url):
                self.assertRedirects(
                    self.client.get(url),
                    f'{login_url}?next={url}',
                )

    def test_list_shows_own_requests_by_user_or_email(self):
        vinculada = self.crear_solicitud(subject='Solicitud vinculada')
        previa = self.crear_solicitud(
            subject='Solicitud antes de la cuenta',
            user=None,
        )
        ajena = self.crear_solicitud(
            subject='Solicitud de otra persona',
            user=self.otro,
            email=self.otro.email,
        )
        self.client.force_login(self.cliente)
        response = self.client.get(self.lista_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, vinculada.subject)
        self.assertContains(response, previa.subject)
        self.assertNotContains(response, ajena.subject)

    def test_list_marks_pending_and_answered_requests(self):
        self.crear_solicitud(subject='Pendiente', status=ContactRequest.Status.PENDIENTE)
        self.crear_solicitud(
            subject='Respondida',
            status=ContactRequest.Status.RESPONDIDA,
            reply='Ya revisamos tu caso.',
        )
        self.client.force_login(self.cliente)
        response = self.client.get(self.lista_url)
        self.assertContains(response, 'Pendiente')
        self.assertContains(response, 'Respondida')
        self.assertEqual(response.context['total_count'], 2)
        self.assertEqual(response.context['pending_count'], 1)

    def test_detail_shows_the_reply_and_mentions_the_email(self):
        contact_request = self.crear_solicitud(
            status=ContactRequest.Status.RESPONDIDA,
            reply='Tu pedido llega mañana.',
        )
        self.client.force_login(self.cliente)
        response = self.client.get(self.detalle_url(contact_request))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, contact_request.message)
        self.assertContains(response, 'Respuesta de Carely')
        self.assertContains(response, contact_request.reply)
        self.assertContains(response, self.cliente.email)

    def test_pending_detail_explains_that_the_reply_is_on_the_way(self):
        contact_request = self.crear_solicitud()
        self.client.force_login(self.cliente)
        response = self.client.get(self.detalle_url(contact_request))
        self.assertContains(response, 'Estamos revisando tu solicitud')
        self.assertNotContains(response, 'Respuesta de Carely')

    def test_other_users_request_returns_404(self):
        ajena = self.crear_solicitud(
            subject='Privada',
            user=self.otro,
            email=self.otro.email,
        )
        self.client.force_login(self.cliente)
        self.assertEqual(self.client.get(self.detalle_url(ajena)).status_code, 404)

    def test_authenticated_submission_is_linked_to_the_user(self):
        self.client.force_login(self.cliente)
        with patch('apps.core.services.GmailService.send_message', return_value=True):
            response = self.client.post(reverse('core:contact'), {
                'name': 'Laura Cliente',
                'email': self.cliente.email,
                'subject': 'Consulta desde la cuenta',
                'message': 'Quiero saber si tienen envíos a mi ciudad.',
            })
        self.assertEqual(response.status_code, 200)
        contact_request = ContactRequest.objects.get(subject='Consulta desde la cuenta')
        self.assertEqual(contact_request.user, self.cliente)

    def test_profile_links_to_my_requests(self):
        self.client.force_login(self.cliente)
        response = self.client.get(reverse('users:profile'))
        self.assertContains(response, self.lista_url)


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

    def test_favicon_usa_la_url_de_estaticos(self):
        response = self.client.get(reverse('core:home'))
        self.assertContains(
            response,
            f'href="{static("core/images/carely-logo.webp")}"',
        )

    def test_extracted_stylesheets_are_linked(self):
        expectations = {
            reverse('cart:cart'): 'cart/css/cart.css',
            reverse('orders:checkout'): 'orders/css/checkout.css',
            reverse('orders:order_detail', args=[self.order.pk]): 'orders/css/order_detail.css',
        }
        for url, static_path in expectations.items():
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), static_path)

    def test_driver_assets_are_loaded(self):
        response = self.client.get(reverse('core:home'))
        self.assertContains(response, static('vendors/driver.js/driver.css'))
        self.assertContains(response, static('vendors/driver.js/driver.js.iife.js'))
        self.assertContains(response, static('js/tour.js'))

    def test_public_tour_pages_have_data_attributes(self):
        self.client.logout()
        pages = {
            reverse('users:login'): 'login',
            reverse('catalog:home'): 'catalog',
            reverse('catalog:product_detail', args=[self.product.slug]): 'product',
        }
        for url, tour in pages.items():
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, f'data-tour="{tour}"')

    def test_authenticated_tour_pages_have_data_attributes(self):
        department = Department.objects.create(api_id=1, name='Cundinamarca')
        city = City.objects.create(api_id=1, name='Bogotá', department=department)
        Address.objects.create(
            user=self.user,
            recipient_name='Jaime Parra',
            address_line='Calle 123',
            city=city,
            department=department,
            is_default=True,
        )
        pages = {
            reverse('cart:cart'): 'cart',
            reverse('orders:checkout'): 'checkout',
            reverse('orders:order_list'): 'orders',
            reverse('orders:order_detail', args=[self.order.pk]): 'order-detail',
            reverse('users:profile'): 'profile',
            reverse('users:address_list'): 'addresses',
            reverse('users:two_factor_setup'): 'two-factor',
        }
        for url, tour in pages.items():
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, f'data-tour="{tour}"')


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

    def test_dashboard_has_tour_marker(self):
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-tour="dashboard"')
        self.assertContains(response, 'id="dashboard-recent-users"')
        self.assertContains(response, 'id="dashboard-recent-orders"')

    def test_site_customization_has_tour_marker(self):
        response = self.client.get(reverse('dashboard:site_customization'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-tour="site-customization"')


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


class ReportExportTests(TestCase):
    """Exportación del reporte de pedidos a PDF (solo administradores)."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin@carely.test',
            email='admin@carely.test',
            password='pass12345',
            role=User.Role.ADMIN,
            is_staff=True,
        )

    def test_admin_descarga_pdf(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('dashboard:report_export'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_cliente_no_exporta(self):
        cliente = User.objects.create_user(
            username='cliente@carely.test',
            email='cliente@carely.test',
            password='pass12345',
            role=User.Role.CLIENT,
        )
        self.client.force_login(cliente)
        response = self.client.get(reverse('dashboard:report_export'))
        self.assertRedirects(response, reverse('core:home'))


def make_png_bytes(width=8, height=8):
    buffer = BytesIO()
    Image.new('RGB', (width, height), (232, 96, 155)).save(buffer, format='PNG')
    return buffer.getvalue()


def make_png_upload(name='portada.png'):
    return SimpleUploadedFile(name, make_png_bytes(), content_type='image/png')


class SiteCustomizationModelTests(TestCase):
    """La configuración de la landing es un singleton con los valores actuales por defecto."""

    def test_load_crea_la_fila_unica_con_el_contenido_actual(self):
        config = SiteCustomization.load()
        self.assertEqual(config.pk, 1)
        self.assertEqual(config.hero_title, 'Cultiva tu')
        self.assertEqual(config.hero_button_text, 'Ver Catalogo')
        self.assertEqual(SiteCustomization.objects.count(), 1)

    def test_save_siempre_escribe_en_la_fila_1(self):
        SiteCustomization(hero_title='Primera').save()
        SiteCustomization(hero_title='Segunda').save()
        self.assertEqual(SiteCustomization.objects.count(), 1)
        self.assertEqual(SiteCustomization.objects.get().hero_title, 'Segunda')

    def test_validate_plain_text_rechaza_etiquetas(self):
        with self.assertRaises(ValidationError):
            validate_plain_text('<script>alert(1)</script>')
        validate_plain_text('Cultiva tu mejor versión')


class SiteCustomizationFormTests(TestCase):

    def setUp(self):
        self.category = Category.objects.create(name='Perfumes', slug='perfumes', icon='bi-test')
        self.product = Product.objects.create(
            category=self.category, name='Aroma', slug='aroma',
            price=Decimal('50000.00'), stock=5, is_active=True,
        )
        self.config = SiteCustomization.load()

    def datos(self, **overrides):
        data = {
            'hero_title': 'Cultiva tu',
            'hero_subtitle': 'Un subtítulo sencillo.',
            'hero_button_text': 'Ver catálogo',
        }
        data.update(overrides)
        return data

    def test_acepta_datos_validos(self):
        form = SiteCustomizationForm(self.datos(), files={'hero_image': make_png_upload()}, instance=self.config)
        self.assertTrue(form.is_valid(), form.errors)

    def test_rechaza_html_en_el_titulo(self):
        form = SiteCustomizationForm(self.datos(hero_title='<b>Hola</b>'), instance=self.config)
        self.assertFalse(form.is_valid())
        self.assertIn('hero_title', form.errors)

    def test_rechaza_javascript_en_un_enlace_social(self):
        form = SiteCustomizationForm(
            self.datos(footer_facebook='javascript:alert(1)'), instance=self.config,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('footer_facebook', form.errors)

    def test_rechaza_mas_de_seis_productos_destacados(self):
        ids = [
            Product.objects.create(
                category=self.category, name=f'Producto {n}', slug=f'producto-{n}',
                price=Decimal('1000.00'),
            ).pk
            for n in range(7)
        ]
        form = SiteCustomizationForm(self.datos(featured_products=ids), instance=self.config)
        self.assertFalse(form.is_valid())
        self.assertIn('featured_products', form.errors)

    def test_rechaza_ids_de_productos_que_no_existen(self):
        form = SiteCustomizationForm(self.datos(featured_products=[999999]), instance=self.config)
        self.assertFalse(form.is_valid())
        self.assertIn('featured_products', form.errors)

    def test_rechaza_archivo_que_no_es_una_imagen(self):
        fake = SimpleUploadedFile('portada.png', b'esto no es una imagen', content_type='image/png')
        form = SiteCustomizationForm(self.datos(), files={'hero_image': fake}, instance=self.config)
        self.assertFalse(form.is_valid())
        self.assertIn('hero_image', form.errors)

    def test_rechaza_extension_no_permitida(self):
        bmp = SimpleUploadedFile('portada.bmp', make_png_bytes(), content_type='image/bmp')
        form = SiteCustomizationForm(self.datos(), files={'hero_image': bmp}, instance=self.config)
        self.assertFalse(form.is_valid())
        self.assertIn('hero_image', form.errors)

    def test_rechaza_imagen_mas_grande_que_el_limite(self):
        with patch('apps.core.forms.MAX_HERO_IMAGE_BYTES', 10):
            form = SiteCustomizationForm(
                self.datos(), files={'hero_image': make_png_upload()}, instance=self.config,
            )
            self.assertFalse(form.is_valid())
        self.assertIn('hero_image', form.errors)

    def test_rechaza_logo_mas_grande_que_el_limite(self):
        with patch('apps.core.forms.MAX_LOGO_IMAGE_BYTES', 10):
            form = SiteCustomizationForm(
                self.datos(), files={'logo': make_png_upload('logo.png')}, instance=self.config,
            )
            self.assertFalse(form.is_valid())
        self.assertIn('logo', form.errors)

    def test_rechaza_isotipo_con_extension_no_permitida(self):
        bmp = SimpleUploadedFile('isotipo.bmp', make_png_bytes(), content_type='image/bmp')
        form = SiteCustomizationForm(
            self.datos(), files={'logo_icon': bmp}, instance=self.config,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('logo_icon', form.errors)


class LandingCustomizationTests(TestCase):
    """La landing lee la configuración guardada y conserva el contenido original sin ella."""

    def setUp(self):
        self.category = Category.objects.create(name='Perfumes', slug='perfumes', icon='bi-test')
        self.featured = Product.objects.create(
            category=self.category, name='Destacado Automatico', slug='destacado-automatico',
            price=Decimal('1000.00'), is_active=True, featured=True,
        )
        self.url = reverse('core:home')

    def test_sin_configuracion_muestra_el_contenido_original(self):
        content = self.client.get(self.url).content.decode()
        self.assertIn('Cultiva tu', content)
        self.assertIn('Productos cuidadosamente seleccionados', content)
        self.assertIn('Ver Catalogo', content)
        self.assertIn('hero-placeholder.png', content)
        for block in DEFAULT_BENEFITS:
            self.assertIn(block['title'], content)
        self.assertIn('Destacado Automatico', content)

    def test_los_cambios_guardados_se_reflejan_en_la_landing(self):
        config = SiteCustomization.load()
        config.hero_title = 'Descubre tu'
        config.hero_subtitle = 'Un subtítulo nuevo.'
        config.hero_button_text = 'Explorar'
        config.hero_image = 'landing/portada.png'
        config.save()

        content = self.client.get(self.url).content.decode()
        self.assertIn('Descubre tu', content)
        self.assertIn('Un subtítulo nuevo.', content)
        self.assertIn('Explorar', content)
        self.assertIn(config.hero_image.url, content)

    def test_productos_seleccionados_reemplazan_a_los_automaticos(self):
        elegido = Product.objects.create(
            category=self.category, name='Producto Elegido', slug='producto-elegido',
            price=Decimal('2000.00'), is_active=True,
        )
        config = SiteCustomization.load()
        config.featured_products.set([elegido])

        content = self.client.get(self.url).content.decode()
        self.assertIn('Producto Elegido', content)
        self.assertNotIn('Destacado Automatico', content)

    def test_producto_inactivo_seleccionado_vuelve_a_los_automaticos(self):
        oculto = Product.objects.create(
            category=self.category, name='Producto Oculto', slug='producto-oculto',
            price=Decimal('2000.00'), is_active=False,
        )
        config = SiteCustomization.load()
        config.featured_products.set([oculto])

        content = self.client.get(self.url).content.decode()
        self.assertNotIn('Producto Oculto', content)
        self.assertIn('Destacado Automatico', content)

    def test_categorias_seleccionadas_filtran_la_seccion(self):
        visible = Category.objects.create(name='Solo visible', slug='solo-visible', icon='bi-a')
        Category.objects.create(name='Sin destacar', slug='sin-destacar', icon='bi-b')
        config = SiteCustomization.load()
        config.featured_categories.set([visible])

        content = self.client.get(self.url).content.decode()
        self.assertIn('class="category-card__name">Solo visible<', content)
        self.assertNotIn('class="category-card__name">Sin destacar<', content)

    def test_beneficio_guardado_reemplaza_el_texto_por_defecto(self):
        LandingBenefit.objects.create(position=1, title='Beneficio nuevo', description='Descripción nueva.')
        content = self.client.get(self.url).content.decode()
        self.assertIn('Beneficio nuevo', content)
        self.assertIn('Descripción nueva.', content)
        self.assertNotIn(DEFAULT_BENEFITS[0]['title'], content)

    def test_pie_de_pagina_usa_los_datos_guardados(self):
        config = SiteCustomization.load()
        config.footer_email = 'hola@carely.test'
        config.footer_phone = '+57 300 111 2233'
        config.footer_address = 'Bogotá, Colombia'
        config.footer_facebook = 'https://facebook.com/carely'
        config.save()

        content = self.client.get(self.url).content.decode()
        self.assertIn('mailto:hola@carely.test', content)
        self.assertIn('tel:+573001112233', content)
        self.assertIn('Bogotá, Colombia', content)
        self.assertIn('https://facebook.com/carely', content)

    def test_pie_de_pagina_vacio_usa_los_valores_del_servidor(self):
        content = self.client.get(self.url).content.decode()
        self.assertIn(f'mailto:{settings.CARELY_EMAIL}', content)

    def test_sin_logos_guardados_usa_los_archivos_por_defecto(self):
        content = self.client.get(self.url).content.decode()
        self.assertIn('carely-logo-text.webp', content)
        self.assertIn('carely-logo.webp', content)

    def test_logos_guardados_se_muestran_en_la_landing(self):
        config = SiteCustomization.load()
        config.logo = 'branding/logo.png'
        config.logo_icon = 'branding/isotipo.png'
        config.save()

        content = self.client.get(self.url).content.decode()
        self.assertIn(config.logo.url, content)
        self.assertIn(config.logo_icon.url, content)
        self.assertNotIn('carely-logo-text.webp', content)


class SiteCustomizationPanelTests(TestCase):
    """Solo los administradores editan la landing; los cambios llegan a la página pública."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin-landing@carely.test', email='admin-landing@carely.test',
            password='pass12345', role=User.Role.ADMIN, is_staff=True,
        )
        self.cliente = User.objects.create_user(
            username='cliente-landing@carely.test', email='cliente-landing@carely.test',
            password='pass12345',
        )
        self.category = Category.objects.create(name='Perfumes', slug='perfumes', icon='bi-test')
        self.product = Product.objects.create(
            category=self.category, name='Aroma', slug='aroma',
            price=Decimal('50000.00'), is_active=True,
        )
        self.url = reverse('dashboard:site_customization')

    def datos_validos(self, **overrides):
        data = {
            'hero_title': 'Cultiva tu',
            'hero_subtitle': 'Subtítulo de prueba.',
            'hero_button_text': 'Ver catálogo',
            'featured_products': [self.product.pk],
            'featured_categories': [self.category.pk],
            'footer_email': '',
            'footer_phone': '',
            'footer_address': '',
            'footer_facebook': '',
            'footer_instagram': '',
            'footer_whatsapp': '',
        }
        for position in (1, 2, 3, 4):
            data[f'title_{position}'] = f'Beneficio {position}'
            data[f'description_{position}'] = f'Descripción {position}'
        data.update(overrides)
        return data

    def test_anonimo_no_puede_entrar(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_cliente_no_puede_ver_ni_editar(self):
        self.client.force_login(self.cliente)
        self.assertEqual(self.client.get(self.url).status_code, 302)

        self.client.post(self.url, self.datos_validos(hero_title='Hackeado'))
        self.assertEqual(SiteCustomization.load().hero_title, 'Cultiva tu')

    def test_admin_ve_el_formulario(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="hero_title"')
        self.assertContains(response, 'name="featured_products"')
        self.assertContains(response, 'name="title_1"')
        self.assertContains(response, 'name="footer_email"')
        self.assertContains(response, 'name="logo"')
        self.assertContains(response, 'name="logo_icon"')
        self.assertContains(response, 'Sección 06')

    def test_admin_guarda_los_cambios_y_se_publican(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url, self.datos_validos(), follow=True)
        self.assertContains(response, 'Los cambios se guardaron')

        config = SiteCustomization.load()
        self.assertEqual(config.hero_button_text, 'Ver catálogo')
        self.assertEqual(list(config.featured_products.all()), [self.product])
        self.assertEqual(LandingBenefit.objects.count(), 4)
        self.assertEqual(LandingBenefit.objects.get(position=2).title, 'Beneficio 2')

        landing = self.client.get(reverse('core:home')).content.decode()
        self.assertIn('Ver catálogo', landing)
        self.assertIn('Beneficio 2', landing)

    def test_datos_invalidos_no_se_guardan(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url, self.datos_validos(hero_title='<script>x</script>'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Revisa los campos marcados')
        self.assertEqual(SiteCustomization.load().hero_title, 'Cultiva tu')

    def test_imagen_subida_se_muestra_en_la_landing(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            self.url, self.datos_validos(hero_image=make_png_upload()), follow=True,
        )
        self.assertContains(response, 'Los cambios se guardaron')

        config = SiteCustomization.load()
        self.assertTrue(config.hero_image.name.startswith('landing/'))
        landing = self.client.get(reverse('core:home')).content.decode()
        self.assertIn(config.hero_image.url, landing)

    def test_logos_subidos_se_guardan_y_se_publican(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            self.url,
            self.datos_validos(
                logo=make_png_upload('logo.png'),
                logo_icon=make_png_upload('isotipo.png'),
            ),
            follow=True,
        )
        self.assertContains(response, 'Los cambios se guardaron')

        config = SiteCustomization.load()
        self.assertTrue(config.logo.name.startswith('branding/'))
        self.assertTrue(config.logo_icon.name.startswith('branding/'))

        content = self.client.get(reverse('core:home')).content.decode()
        self.assertIn(config.logo.url, content)
        self.assertIn(config.logo_icon.url, content)

    def test_reemplazar_la_imagen_borra_la_anterior_del_almacenamiento(self):
        from django.core.files.storage import default_storage

        anterior = default_storage.save('landing/anterior.png', make_png_upload('anterior.png'))
        config = SiteCustomization.load()
        config.hero_image = anterior
        config.save()

        self.client.force_login(self.admin)
        self.client.post(self.url, self.datos_validos(hero_image=make_png_upload('nueva.png')))

        self.assertFalse(default_storage.exists(anterior))
        self.assertTrue(default_storage.exists(SiteCustomization.load().hero_image.name))


def hidden_featured_ids(html):
    return {int(v) for v in re.findall(r'type="hidden" name="featured_products" value="(\d+)"', html)}


def checked_featured_ids(html):
    # Entre `value` y `checked` hay un salto de línea: por eso \s+.
    return {int(v) for v in re.findall(r'name="featured_products" value="(\d+)"\s+checked', html)}


def browser_featured_values(html):
    """Lo que el navegador enviaría en `featured_products` desde esa pantalla."""
    return sorted(hidden_featured_ids(html) | checked_featured_ids(html))


class SiteCustomizationPickerTests(TestCase):
    """Paginador, filtro y selección de productos destacados en el panel."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin-picker@carely.test', email='admin-picker@carely.test',
            password='pass12345', role=User.Role.ADMIN, is_staff=True,
        )
        self.cliente = User.objects.create_user(
            username='cliente-picker@carely.test', email='cliente-picker@carely.test',
            password='pass12345',
        )
        self.client.force_login(self.admin)
        self.url = reverse('dashboard:site_customization')
        self.perfumes = Category.objects.create(name='Perfumes', slug='perfumes', icon='bi-test')
        self.maquillaje = Category.objects.create(name='Maquillaje', slug='maquillaje', icon='bi-brush')
        # Catorce productos con nombres ordenables: 12 en la página 1, 2 en la 2.
        self.productos = [
            Product.objects.create(
                category=self.perfumes, name=f'Producto {n:02d}', slug=f'producto-{n:02d}',
                price=Decimal('1000.00'), is_active=True,
            )
            for n in range(1, 15)
        ]

    def datos(self, **extra):
        data = {
            'hero_title': 'Cultiva tu',
            'hero_subtitle': 'Subtítulo de prueba.',
            'hero_button_text': 'Ver catálogo',
            'footer_email': '', 'footer_phone': '', 'footer_address': '',
            'footer_facebook': '', 'footer_instagram': '', 'footer_whatsapp': '',
        }
        for position in (1, 2, 3, 4):
            data[f'title_{position}'] = f'Beneficio {position}'
            data[f'description_{position}'] = f'Descripción {position}'
        data.update(extra)
        return data

    def test_muestra_doce_productos_por_pagina(self):
        response = self.client.get(self.url)
        page = response.context['picker']['page']
        self.assertEqual(page.paginator.num_pages, 2)
        self.assertEqual(len(page.object_list), 12)
        self.assertEqual(response.content.decode().count('name="featured_products" value='), 12)

    def test_segunda_pagina_muestra_el_resto(self):
        response = self.client.post(self.url, {'browse_page': '2'})
        page = response.context['picker']['page']
        self.assertEqual(page.number, 2)
        self.assertEqual([p.name for p in page.object_list], ['Producto 13', 'Producto 14'])

    def test_numero_de_pagina_invalido_no_rompe_la_pantalla(self):
        self.assertEqual(self.client.post(self.url, {'browse_page': 'abc'}).context['picker']['page'].number, 1)
        self.assertEqual(self.client.post(self.url, {'browse_page': '999'}).context['picker']['page'].number, 2)

    def test_paginador_solo_aparece_si_hay_mas_de_una_pagina(self):
        self.assertContains(self.client.get(self.url), 'class="site-pager"')
        filtrado = self.client.post(self.url, {'browse_page': '1', 'product_q': 'Producto 1'})
        self.assertNotContains(filtrado, 'class="site-pager"')

    def test_filtro_por_nombre(self):
        response = self.client.post(self.url, {'browse_page': '1', 'product_q': 'Producto 1'})
        nombres = {p.name for p in response.context['picker']['page'].object_list}
        self.assertEqual(nombres, {f'Producto {n}' for n in range(10, 15)})

    def test_filtro_por_categoria(self):
        self.productos[-1].category = self.maquillaje
        self.productos[-1].save()
        response = self.client.post(self.url, {'browse_page': '1', 'product_category': str(self.maquillaje.pk)})
        nombres = [p.name for p in response.context['picker']['page'].object_list]
        self.assertEqual(nombres, ['Producto 14'])

    def test_filtro_sin_resultados_lo_indica(self):
        response = self.client.post(self.url, {'browse_page': '1', 'product_q': 'zzzz'})
        self.assertContains(response, 'No hay productos que coincidan con el filtro.')

    def test_solo_seleccionados_muestra_los_marcados(self):
        self.client.post(self.url, {'browse_page': '1', 'featured_products': [self.productos[4].pk]})
        response = self.client.post(self.url, {
            'browse_page': '1', 'product_selected': '1', 'featured_products': [self.productos[4].pk],
        })
        nombres = [p.name for p in response.context['picker']['page'].object_list]
        self.assertEqual(nombres, ['Producto 05'])

    def test_seleccion_se_mantiene_al_cambiar_de_pagina(self):
        p1, p13 = self.productos[0], self.productos[12]

        # 1) Marco el producto 1 en la página 1 y paso a la página 2.
        resp1 = self.client.post(self.url, {'browse_page': '2', 'featured_products': [p1.pk]})
        self.assertIn(p1.pk, hidden_featured_ids(resp1.content.decode()))

        # 2) En la página 2 marco el producto 13.
        resp2 = self.client.post(self.url, {
            'browse_page': '2',
            'featured_products': browser_featured_values(resp1.content.decode()) + [p13.pk],
        })
        html2 = resp2.content.decode()
        self.assertIn(p1.pk, hidden_featured_ids(html2))
        self.assertIn(p13.pk, checked_featured_ids(html2))

        # 3) Guardo: ambos deben quedar seleccionados.
        resp3 = self.client.post(
            self.url,
            self.datos(featured_products=browser_featured_values(html2)),
            follow=True,
        )
        self.assertContains(resp3, 'Los cambios se guardaron')
        self.assertEqual(
            set(SiteCustomization.load().featured_products.values_list('pk', flat=True)),
            {p1.pk, p13.pk},
        )

    def test_navegar_no_guarda_nada(self):
        self.client.post(self.url, {
            'browse_page': '2',
            'hero_title': 'Titulo sin guardar',
            'featured_products': [self.productos[0].pk],
        })
        config = SiteCustomization.load()
        self.assertEqual(config.hero_title, 'Cultiva tu')
        self.assertEqual(config.featured_products.count(), 0)

    def test_seleccion_guardada_aparece_marcada_al_abrir_el_panel(self):
        config = SiteCustomization.load()
        config.featured_products.set([self.productos[2]])
        html = self.client.get(self.url).content.decode()
        self.assertIn(self.productos[2].pk, checked_featured_ids(html))
        self.assertIn('1 de 6 seleccionados', html)

    def test_ids_inexistentes_no_se_reenvian(self):
        response = self.client.post(self.url, {'browse_page': '1', 'featured_products': ['999999']})
        self.assertNotIn('value="999999"', response.content.decode())

    def test_guardar_con_mas_de_seis_no_cambia_la_seleccion(self):
        config = SiteCustomization.load()
        config.featured_products.set([self.productos[0]])
        ids = [p.pk for p in self.productos[:7]]
        response = self.client.post(self.url, self.datos(featured_products=ids))
        self.assertContains(response, 'Revisa los campos marcados')
        self.assertEqual(list(config.featured_products.values_list('pk', flat=True)), [self.productos[0].pk])

    def test_cliente_no_puede_paginar_ni_filtrar(self):
        self.client.force_login(self.cliente)
        response = self.client.post(self.url, {'browse_page': '2', 'product_q': 'x'})
        self.assertEqual(response.status_code, 302)


class PageWindowTests(TestCase):
    """La ventana del paginador no crece con el catálogo."""

    class FakePage:
        def __init__(self, number, num_pages):
            self.number = number
            self.paginator = type('P', (), {'num_pages': num_pages})()

    def window(self, number, num_pages):
        from apps.core.customization_views import page_window

        return page_window(self.FakePage(number, num_pages))

    def test_pocas_paginas_se_muestran_todas(self):
        self.assertEqual(self.window(1, 3), [1, 2, 3])

    def test_muchas_paginas_muestran_hueco_y_extremos(self):
        self.assertEqual(self.window(1, 20), [1, 2, 3, None, 20])
        self.assertEqual(self.window(10, 20), [1, None, 8, 9, 10, 11, 12, None, 20])
        self.assertEqual(self.window(20, 20), [1, None, 18, 19, 20])
