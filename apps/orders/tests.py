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

    def test_checkout_envia_correo(self):
        from django.core import mail
        from django.test import TransactionTestCase

        # Flush outbox
        mail.outbox = []

        # We must use captureOnCommitCallbacks to trigger on_commit in standard TestCase
        with self.captureOnCommitCallbacks(execute=True):
            order = checkout_cart(self.user, self.address.id, site_url='http://localhost:8000')

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.subject, f'¡Tu pedido #{order.id} está confirmado!')
        self.assertEqual(email.to, [self.user.email])
        
        # Verify content contains required fields
        self.assertIn(str(order.id), email.body)
        self.assertIn(self.prod1.name, email.body)
        self.assertIn(str(int(order.total)), email.body)
        self.assertIn(self.address.address_line, email.body)
        self.assertEqual(order.user.email, self.user.email)

    def test_checkout_error_correo_no_revierte_pedido(self):
        from unittest.mock import patch
        
        # Patcheamos GmailService.send_message para que tire error.
        with patch('apps.orders.services.GmailService.send_message') as mock_send:
            mock_send.side_effect = Exception("Fallo de red al enviar el correo")
            
            with self.captureOnCommitCallbacks(execute=True):
                order = checkout_cart(self.user, self.address.id)
            
        # El pedido DEBIÓ procesarse completamente a pesar del error de envío.
        self.assertEqual(Order.objects.filter(id=order.id).count(), 1)
        self.assertEqual(self.cart.items.count(), 0)
        self.assertTrue(mock_send.called)

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


# ─────────────────────────────────────────────────────────────────────────────
# TESTS DE CUPONES
# ─────────────────────────────────────────────────────────────────────────────

from django.utils import timezone
from datetime import timedelta
from apps.orders.models import Coupon
from apps.orders.services import validate_coupon, InvalidCouponError


def make_coupon(
    code='TEST10',
    discount_type=Coupon.DiscountType.PERCENTAGE,
    discount_value='10.00',
    is_active=True,
    usage_limit=None,
    usage_count=0,
    minimum_purchase='0.00',
    valid_from=None,
    valid_until=None,
):
    return Coupon.objects.create(
        code=code,
        discount_type=discount_type,
        discount_value=Decimal(discount_value),
        is_active=is_active,
        usage_limit=usage_limit,
        usage_count=usage_count,
        minimum_purchase=Decimal(minimum_purchase),
        valid_from=valid_from,
        valid_until=valid_until,
    )


class CouponModelTests(TestCase):
    """Tests del modelo Coupon y su lógica de validación / cálculo."""

    # 1. Crear cupón porcentual
    def test_crear_cupon_porcentual(self):
        c = make_coupon('PCT10', discount_type=Coupon.DiscountType.PERCENTAGE, discount_value='10.00')
        self.assertEqual(c.code, 'PCT10')
        self.assertEqual(c.discount_type, Coupon.DiscountType.PERCENTAGE)

    # 2. Crear cupón de valor fijo
    def test_crear_cupon_fijo(self):
        c = make_coupon('FIJO5000', discount_type=Coupon.DiscountType.FIXED, discount_value='5000.00')
        self.assertEqual(c.discount_type, Coupon.DiscountType.FIXED)

    # 3. Aplicar cupón válido
    def test_aplicar_cupon_valido(self):
        c = make_coupon('VALID', discount_value='10.00')
        coupon, discount = validate_coupon('VALID', Decimal('100.00'))
        self.assertEqual(discount, Decimal('10.00'))

    # 4. Rechazar cupón inexistente
    def test_rechazar_cupon_inexistente(self):
        with self.assertRaises(InvalidCouponError):
            validate_coupon('NOEXISTE', Decimal('100.00'))

    # 5. Rechazar cupón inactivo
    def test_rechazar_cupon_inactivo(self):
        make_coupon('INACTIVO', is_active=False)
        with self.assertRaises(InvalidCouponError):
            validate_coupon('INACTIVO', Decimal('100.00'))

    # 6. Rechazar cupón expirado
    def test_rechazar_cupon_expirado(self):
        past = timezone.now() - timedelta(days=1)
        make_coupon('EXPIRADO', valid_until=past)
        with self.assertRaises(InvalidCouponError):
            validate_coupon('EXPIRADO', Decimal('100.00'))

    # 7. Rechazar cupón aún no vigente
    def test_rechazar_cupon_no_vigente(self):
        future = timezone.now() + timedelta(days=10)
        make_coupon('FUTURO', valid_from=future)
        with self.assertRaises(InvalidCouponError):
            validate_coupon('FUTURO', Decimal('100.00'))

    # 8. Rechazar si no se alcanza minimum_purchase
    def test_rechazar_minimo_compra_no_alcanzado(self):
        make_coupon('MINIMO', minimum_purchase='200.00')
        with self.assertRaises(InvalidCouponError):
            validate_coupon('MINIMO', Decimal('100.00'))

    # 9. Rechazar porcentaje > 100
    def test_rechazar_porcentaje_mayor_100(self):
        c = make_coupon('PCT150', discount_value='150.00')
        valid, reason = c.is_valid(Decimal('100.00'))
        self.assertFalse(valid)

    # 10. Impedir descuento negativo
    def test_no_descuento_negativo(self):
        c = make_coupon('PCT10', discount_value='10.00')
        discount = c.calculate_discount(Decimal('100.00'))
        self.assertGreaterEqual(discount, Decimal('0.00'))

    # 11. Impedir total negativo (descuento capped al subtotal)
    def test_no_total_negativo_descuento_fijo_mayor_subtotal(self):
        c = make_coupon('FIJO9999', discount_type=Coupon.DiscountType.FIXED, discount_value='9999.00')
        discount = c.calculate_discount(Decimal('50.00'))
        # Descuento se limita al subtotal
        self.assertEqual(discount, Decimal('50.00'))

    # 12. Calcular correctamente porcentaje
    def test_calcular_porcentaje_correcto(self):
        c = make_coupon('PCT20', discount_value='20.00')
        discount = c.calculate_discount(Decimal('100.00'))
        self.assertEqual(discount, Decimal('20.00'))

    # 13. Calcular correctamente descuento fijo
    def test_calcular_fijo_correcto(self):
        c = make_coupon('FIJO5K', discount_type=Coupon.DiscountType.FIXED, discount_value='5000.00')
        discount = c.calculate_discount(Decimal('20000.00'))
        self.assertEqual(discount, Decimal('5000.00'))

    # Normalizar código a mayúsculas
    def test_codigo_normalizado_mayusculas(self):
        c = Coupon.objects.create(
            code='carely10',
            discount_type=Coupon.DiscountType.PERCENTAGE,
            discount_value=Decimal('10'),
        )
        self.assertEqual(c.code, 'CARELY10')


class CouponCheckoutIntegrationTests(TestCase):
    """Tests de integración: cupón en el flujo checkout_cart."""

    def setUp(self):
        self.user = make_user('buyer@carely.com')
        self.address = make_address(self.user, recipient_name='Buyer', address_line='Calle Compra')
        self.prod = make_product('Tónico', price='100.00', stock=10)
        self.cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=self.cart, product=self.prod, quantity=2)
        # subtotal = 200.00

    # 14 & 15. Order conserva coupon_code y discount_amount
    def test_order_guarda_coupon_code_y_discount(self):
        coupon = make_coupon('SAVE10', discount_value='10.00')
        order = checkout_cart(self.user, self.address.id, coupon_code='SAVE10')
        order.refresh_from_db()
        self.assertEqual(order.coupon_code, 'SAVE10')
        self.assertEqual(order.coupon, coupon)
        self.assertEqual(order.discount_amount, Decimal('20.00'))  # 10% de 200

    # 16. Total final correcto
    def test_total_final_correcto_con_cupon(self):
        make_coupon('SAVE10PCT', discount_value='10.00')
        order = checkout_cart(self.user, self.address.id, coupon_code='SAVE10PCT')
        order.refresh_from_db()
        # subtotal 200, discount 20, total 180
        self.assertEqual(order.total, Decimal('180.00'))

    # 17. No modifica unit_price de OrderItem
    def test_no_modifica_unit_price_en_items(self):
        make_coupon('PCT50', discount_value='50.00')
        order = checkout_cart(self.user, self.address.id, coupon_code='PCT50')
        for item in order.items.all():
            # Precio original 100. No debe cambiarse aunque haya 50% de descuento.
            self.assertEqual(item.unit_price, Decimal('100.00'))

    # 18. Sin cupón funciona exactamente igual que antes
    def test_checkout_sin_cupon_funciona_igual(self):
        order = checkout_cart(self.user, self.address.id)
        order.refresh_from_db()
        self.assertEqual(order.coupon_code, '')
        self.assertIsNone(order.coupon)
        self.assertEqual(order.discount_amount, Decimal('0.00'))
        self.assertEqual(order.total, Decimal('200.00'))

    # 19. Cupón debe revalidarse en checkout (no confiar en sesión)
    def test_cupon_invalido_al_confirmar_rechaza_pedido(self):
        # Crear cupón expirado
        past = timezone.now() - timedelta(seconds=1)
        make_coupon('EXPIRADOC', valid_until=past)
        with self.assertRaises(InvalidCouponError):
            checkout_cart(self.user, self.address.id, coupon_code='EXPIRADOC')
        # No debe haberse creado ningún pedido
        self.assertEqual(Order.objects.count(), 0)

    # 21. Si checkout falla, no se contabiliza el uso del cupón
    def test_uso_cupon_no_contabilizado_si_checkout_falla(self):
        coupon = make_coupon('USETEST', usage_limit=5, usage_count=0)
        # Provocar fallo: vaciar carrito antes de checkout
        self.cart.items.all().delete()
        with self.assertRaises(EmptyCartError):
            checkout_cart(self.user, self.address.id, coupon_code='USETEST')
        coupon.refresh_from_db()
        self.assertEqual(coupon.usage_count, 0)

    # 22. Validar usage_limit
    def test_cupon_alcanza_limite_de_usos(self):
        # usage_count igual al límite
        make_coupon('AGOTADO', usage_limit=1, usage_count=1)
        with self.assertRaises(InvalidCouponError):
            checkout_cart(self.user, self.address.id, coupon_code='AGOTADO')

    # 24. Usuario no puede usar info de otro para descuentos
    def test_aislamiento_usuario_no_accede_info_ajena(self):
        user2 = make_user('otro@carely.com')
        addr2 = make_address(user2, recipient_name='Otro', address_line='Otra Dir')
        coupon = make_coupon('COMUN', discount_value='10.00')

        # user (sin carrito del user2) no puede usar la dirección de user2
        with self.assertRaises(InvalidAddressError):
            checkout_cart(self.user, addr2.id, coupon_code='COMUN')

    # 25. Cancelar pedido NO devuelve uso del cupón (política definida)
    def test_cancelar_pedido_no_devuelve_uso_cupon(self):
        from apps.orders.models import OrderStatusHistory
        coupon = make_coupon('CANCELTEST', usage_limit=5, usage_count=0)
        order = checkout_cart(self.user, self.address.id, coupon_code='CANCELTEST')
        coupon.refresh_from_db()
        self.assertEqual(coupon.usage_count, 1)

        # Cancelar pedido
        order.status = Order.Status.CANCELADO
        order.save(update_fields=['status'])

        # usage_count NO debe cambiar (política: cancelación no devuelve usos)
        coupon.refresh_from_db()
        self.assertEqual(coupon.usage_count, 1)

    # 20. Si carrito cambia después de aplicar cupón, el descuento se recalcula
    # (esto se prueba a nivel unitario en validate_coupon)
    def test_recalculo_si_subtotal_cambia_minimum_purchase(self):
        make_coupon('MINPURCH', discount_value='10.00', minimum_purchase='300.00')
        # Subtotal = 200, mínimo = 300 → inválido
        with self.assertRaises(InvalidCouponError):
            validate_coupon('MINPURCH', Decimal('200.00'))
        # Con subtotal suficiente → válido
        coupon, discount = validate_coupon('MINPURCH', Decimal('300.00'))
        self.assertEqual(discount, Decimal('30.00'))

