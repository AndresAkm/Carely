from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.catalog.models import Category, Product
from apps.cart.models import Cart, CartItem
from apps.users.models import Address
from apps.orders.models import Order, OrderItem
from apps.inventory.services import InventoryService, InsufficientStockError
from apps.orders.services import checkout_cart, EmptyCartError, InvalidAddressError
from unittest.mock import patch


User = get_user_model()

def make_user(email='test@carely.com'):
    return User.objects.create_user(
        username=email.split('@')[0] + str(hash(email)),
        email=email,
        password='password123',
        first_name='Test',
        last_name='User'
    )

def make_category(name='TestCat'):
    cat, _ = Category.objects.get_or_create(name=name, defaults={'icon': 'box'})
    return cat

def make_product(name='Proc', price='10.0', stock=10):
    cat = make_category()
    p = Product.objects.create(name=name, price=Decimal(price), stock=0, category=cat)
    if stock > 0:
        InventoryService.add_stock(product=p, quantity=stock, reason='init')
    return p

def make_address(user, recipient_name='T', address_line='Q', active=True):
    return Address.objects.create(
        user=user, 
        recipient_name=recipient_name, 
        address_line=address_line,
        city='City',
        department='Dept',
        postal_code='123',
        phone='1234567',
        instructions='Inst',
        is_active=active
    )


class CheckoutServiceTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.user2 = make_user('other@example.com')
        self.address = make_address(self.user, recipient_name='Pedro', address_line='Calle 123')
        self.prod1 = make_product('Crema', price='50.00', stock=10)
        self.prod2 = make_product('Serum', price='30.00', stock=5)
        
        self.cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=self.cart, product=self.prod1, quantity=2)
        CartItem.objects.create(cart=self.cart, product=self.prod2, quantity=1)
        
    def test_checkout_exitoso(self):
        order = checkout_cart(self.user, self.address.id, 'Entregar mañana')
        
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(order.user, self.user)
        self.assertEqual(order.notes, 'Entregar mañana')
        # Total = (50*2) + (30*1) = 130
        self.assertEqual(order.total, Decimal('130.00'))
        
        # Test de items y snapshots (precio y nombre)
        self.assertEqual(order.items.count(), 2)
        item1 = order.items.get(product=self.prod1)
        self.assertEqual(item1.unit_price, Decimal('50.00'))
        self.assertEqual(item1.product_name, 'Crema')
        self.assertEqual(item1.quantity, 2)
        self.assertEqual(item1.subtotal, Decimal('100.00'))
        
        # Test de vaciado de carrito
        self.assertEqual(self.cart.items.count(), 0)
        
        # Test de descuento correcto de stock
        self.prod1.refresh_from_db()
        self.assertEqual(self.prod1.stock, 8)
        self.prod2.refresh_from_db()
        self.assertEqual(self.prod2.stock, 4)
        
    def test_snapshot_direccion(self):
        order = checkout_cart(self.user, self.address.id)
        # Cambiamos la direccion después
        self.address.recipient_name = 'Juan'
        self.address.save()
        
        order.refresh_from_db()
        # Debe contener la direccion vieja y formateada
        self.assertIn('Pedro', order.shipping_address)
        self.assertNotIn('Juan', order.shipping_address)
        self.assertIn('Calle 123', order.shipping_address)
        self.assertIn('City, Dept', order.shipping_address)

    def test_carrito_vacio(self):
        self.cart.items.all().delete()
        with self.assertRaisesMessage(EmptyCartError, 'El carrito está vacío.'):
            checkout_cart(self.user, self.address.id)
        
        self.assertEqual(Order.objects.count(), 0)

    def test_direccion_inexistente_o_ajena(self):
        address2 = make_address(self.user2, recipient_name='Mario')
        with self.assertRaises(InvalidAddressError):
            checkout_cart(self.user, address2.id)

    def test_stock_insuficiente_y_rollback_completo(self):
        # Tratar de comprar más de lo que hay
        CartItem.objects.filter(product=self.prod1).update(quantity=15)
        
        with self.assertRaises(InsufficientStockError):
            checkout_cart(self.user, self.address.id)
            
        # Comprobar ROLLBACK (aislamiento y fallas)
        self.assertEqual(Order.objects.count(), 0)
        # Carrito debe seguir vivo
        self.assertEqual(self.cart.items.count(), 2)
        # Stock de prod2 NO debe haberse descontado aunque pudo procesarse antes o despues
        self.prod2.refresh_from_db()
        self.assertEqual(self.prod2.stock, 5)

    def test_aislamiento_entre_usuarios(self):
        cart2 = Cart.objects.create(user=self.user2)
        CartItem.objects.create(cart=cart2, product=self.prod2, quantity=1)
        
        # User 1 checkout
        checkout_cart(self.user, self.address.id)
        
        self.assertEqual(self.cart.items.count(), 0)
        self.assertEqual(cart2.items.count(), 1)
        self.prod2.refresh_from_db()
        self.assertEqual(self.prod2.stock, 4)

class OrderViewsTests(TestCase):
    def setUp(self):
        self.user = make_user('tester@carely.com')
        self.user2 = make_user('other@example.com')
        self.address = make_address(self.user, recipient_name='T', address_line='Line')
        
    def test_listado_autenticado_y_vacio(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('orders:order_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Mis Pedidos')
        self.assertEqual(len(response.context['orders']), 0)
        
    def test_detalle_propio_con_snapshots(self):
        order = Order.objects.create(user=self.user, total=Decimal('100'), shipping_address='Snapshot de dirección')
        order.items.create(product=make_product(), product_name='Producto X', unit_price=Decimal('100'), quantity=1)
        
        self.client.force_login(self.user)
        res = self.client.get(reverse('orders:order_detail', args=[order.id]))
        self.assertEqual(res.status_code, 200)
        
        # Validar snapshots
        self.assertContains(res, 'Snapshot de dirección')
        self.assertContains(res, 'Producto X')
        
    def test_aislamiento_pedido_ajeno(self):
        order = Order.objects.create(user=self.user2, total=Decimal('10'))
        
        self.client.force_login(self.user)
        res = self.client.get(reverse('orders:order_detail', args=[order.id]))
        self.assertEqual(res.status_code, 404)
