from decimal import Decimal

from django.urls import reverse
from rest_framework.test import APITestCase

from apps.cart.models import Cart
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
        self.client.force_login(self.user_a)
        self.assertEqual(self.client.get('/accounts/logout/').status_code, 405)
        self.assertEqual(self.client.post('/accounts/logout/').status_code, 302)
