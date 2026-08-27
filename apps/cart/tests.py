"""
Tests del módulo de carrito.

Se ejecutan con:
    python manage.py test apps.cart --settings=config.settings.test
"""
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.catalog.models import Category, Product
from apps.users.models import User

from .models import Cart, CartItem
from .services import CartStockError, add_item, get_or_create_cart, remove_item, update_item_quantity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_category():
    cat, _ = Category.objects.get_or_create(name='TestCat', defaults={'icon': 'bi-box'})
    return cat


def make_product(stock=10, **kwargs):
    cat = kwargs.pop('category', None) or make_category()
    return Product.objects.create(
        category=cat,
        name=kwargs.get('name', 'Producto Test'),
        price=Decimal('15.50'),
        stock=stock,
        is_active=True,
    )


def make_user(email='user@carely.test', role=User.Role.CLIENT):
    return User.objects.create_user(
        username=email,
        email=email,
        password='TestPass1!',
        role=role,
    )


def make_admin():
    return make_user(email='admin@carely.test', role=User.Role.ADMIN)


# ---------------------------------------------------------------------------
# 1. CartService — get_or_create_cart
# ---------------------------------------------------------------------------

class GetOrCreateCartTests(TestCase):

    def test_crea_carrito_para_nuevo_usuario(self):
        user = make_user()
        cart = get_or_create_cart(user)
        self.assertIsNotNone(cart)
        self.assertEqual(cart.user, user)
        self.assertEqual(Cart.objects.count(), 1)

    def test_retorna_carrito_existente(self):
        user = make_user()
        cart1 = get_or_create_cart(user)
        cart2 = get_or_create_cart(user)
        self.assertEqual(cart1.pk, cart2.pk)
        self.assertEqual(Cart.objects.count(), 1)


# ---------------------------------------------------------------------------
# 2. CartService — add_item
# ---------------------------------------------------------------------------

class AddItemTests(TestCase):

    def setUp(self):
        self.user = make_user()
        self.product = make_product(stock=10)

    def test_add_crea_item(self):
        item = add_item(self.user, self.product, quantity=2)
        self.assertEqual(item.quantity, 2)
        self.assertEqual(CartItem.objects.count(), 1)

    def test_add_acumula_cantidad(self):
        add_item(self.user, self.product, quantity=3)
        add_item(self.user, self.product, quantity=4)
        item = CartItem.objects.get(cart__user=self.user, product=self.product)
        self.assertEqual(item.quantity, 7)

    def test_add_crea_carrito_automaticamente(self):
        self.assertFalse(Cart.objects.filter(user=self.user).exists())
        add_item(self.user, self.product, quantity=1)
        self.assertTrue(Cart.objects.filter(user=self.user).exists())

    def test_add_supera_stock_lanza_error(self):
        with self.assertRaises(CartStockError):
            add_item(self.user, self.product, quantity=11)

    def test_add_cantidad_cero_lanza_error(self):
        with self.assertRaises(ValueError):
            add_item(self.user, self.product, quantity=0)

    def test_add_cantidad_negativa_lanza_error(self):
        with self.assertRaises(ValueError):
            add_item(self.user, self.product, quantity=-1)

    def test_add_acumulado_supera_stock_lanza_error(self):
        add_item(self.user, self.product, quantity=8)
        with self.assertRaises(CartStockError):
            add_item(self.user, self.product, quantity=5)

    def test_subtotal_calculado_correctamente(self):
        item = add_item(self.user, self.product, quantity=3)
        self.assertEqual(item.subtotal, Decimal('15.50') * 3)


# ---------------------------------------------------------------------------
# 3. CartService — update_item_quantity
# ---------------------------------------------------------------------------

class UpdateItemTests(TestCase):

    def setUp(self):
        self.user = make_user()
        self.product = make_product(stock=10)
        add_item(self.user, self.product, quantity=3)

    def test_actualiza_cantidad(self):
        item = update_item_quantity(self.user, self.product, quantity=5)
        self.assertIsNotNone(item)
        self.assertEqual(item.quantity, 5)

    def test_cantidad_cero_elimina_item(self):
        result = update_item_quantity(self.user, self.product, quantity=0)
        self.assertIsNone(result)
        self.assertEqual(CartItem.objects.count(), 0)

    def test_cantidad_negativa_elimina_item(self):
        result = update_item_quantity(self.user, self.product, quantity=-1)
        self.assertIsNone(result)

    def test_superar_stock_lanza_error(self):
        with self.assertRaises(CartStockError):
            update_item_quantity(self.user, self.product, quantity=11)

    def test_item_inexistente_retorna_none(self):
        other_product = make_product(stock=5, name='Otro')
        result = update_item_quantity(self.user, other_product, quantity=1)
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# 4. CartService — remove_item
# ---------------------------------------------------------------------------

class RemoveItemTests(TestCase):

    def setUp(self):
        self.user = make_user()
        self.product = make_product(stock=10)
        add_item(self.user, self.product, quantity=2)

    def test_elimina_item(self):
        removed = remove_item(self.user, self.product)
        self.assertTrue(removed)
        self.assertEqual(CartItem.objects.count(), 0)

    def test_item_inexistente_retorna_false(self):
        other_product = make_product(stock=5, name='Otro')
        removed = remove_item(self.user, other_product)
        self.assertFalse(removed)

    def test_total_baja_a_cero_tras_eliminar(self):
        cart = Cart.objects.get(user=self.user)
        remove_item(self.user, self.product)
        self.assertEqual(cart.total, 0)


# ---------------------------------------------------------------------------
# 5. Cart.total
# ---------------------------------------------------------------------------

class CartTotalTests(TestCase):

    def test_total_suma_subtotales(self):
        user = make_user()
        cat = make_category()
        p1 = make_product(stock=10, name='P1', category=cat)
        p2 = make_product(stock=10, name='P2', category=cat)
        p2.price = Decimal('20.00')
        p2.save()

        add_item(user, p1, quantity=2)    # 15.50 * 2 = 31.00
        add_item(user, p2, quantity=1)   # 20.00 * 1 = 20.00
        cart = Cart.objects.get(user=user)
        # Refetch items
        self.assertEqual(cart.total, Decimal('51.00'))


# ---------------------------------------------------------------------------
# 6. Vistas web — permisos y comportamiento
# ---------------------------------------------------------------------------

class CartViewsTests(TestCase):

    def setUp(self):
        self.user = make_user()
        self.product = make_product(stock=10)

    def test_carrito_requiere_login(self):
        response = self.client.get(reverse('cart:cart'))
        self.assertRedirects(response, f'/accounts/login/?next=/carrito/')

    def test_carrito_vacio_muestra_estado_vacio(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('cart:cart'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'vacío')

    def test_agregar_producto_al_carrito(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('cart:add', args=[self.product.pk]),
            {'quantity': 2, 'next': '/carrito/'},
            follow=True,
        )
        self.assertEqual(CartItem.objects.filter(cart__user=self.user).count(), 1)
        item = CartItem.objects.get(cart__user=self.user, product=self.product)
        self.assertEqual(item.quantity, 2)

    def test_agregar_sin_login_redirige_a_login(self):
        response = self.client.post(
            reverse('cart:add', args=[self.product.pk]),
            {'quantity': 1},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_agregar_supera_stock_retorna_error(self):
        self.client.force_login(self.user)
        self.client.post(
            reverse('cart:add', args=[self.product.pk]),
            {'quantity': 999},
        )
        # El item no se crea (stock insuficiente)
        self.assertEqual(CartItem.objects.filter(cart__user=self.user).count(), 0)

    def test_eliminar_item_funciona(self):
        add_item(self.user, self.product, quantity=2)
        self.client.force_login(self.user)
        self.client.post(reverse('cart:remove', args=[self.product.pk]))
        self.assertEqual(CartItem.objects.filter(cart__user=self.user).count(), 0)

    def test_actualizar_cantidad_funciona(self):
        add_item(self.user, self.product, quantity=2)
        self.client.force_login(self.user)
        self.client.post(
            reverse('cart:update', args=[self.product.pk]),
            {'quantity': 5},
        )
        item = CartItem.objects.get(cart__user=self.user, product=self.product)
        self.assertEqual(item.quantity, 5)

    def test_cart_add_json_response(self):
        """add via AJAX retorna JSON con ok=True y cart_count."""
        self.client.force_login(self.user)
        import json
        response = self.client.post(
            reverse('cart:add', args=[self.product.pk]),
            data=json.dumps({'quantity': 3}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['cart_count'], 3)

    def test_cart_add_json_stock_error(self):
        """add via AJAX con exceso de stock retorna 400."""
        self.client.force_login(self.user)
        import json
        response = self.client.post(
            reverse('cart:add', args=[self.product.pk]),
            data=json.dumps({'quantity': 999}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['ok'])

    def test_carrito_no_comparte_entre_usuarios(self):
        """El carrito de un usuario no muestra items de otro."""
        user2 = make_user(email='user2@carely.test')
        add_item(self.user, self.product, quantity=3)

        self.client.force_login(user2)
        response = self.client.get(reverse('cart:cart'))
        self.assertNotContains(response, self.product.name)
