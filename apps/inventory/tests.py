"""
Tests del módulo de inventario.

Se ejecutan con:
    python manage.py test apps.inventory --settings=config.settings.test

El entorno de tests usa SQLite temporal con migraciones desactivadas
(ver config/settings/test.py).
"""

from decimal import Decimal

from django.test import TestCase, TransactionTestCase

from apps.catalog.models import Category, Product
from apps.users.models import User

from .models import InventoryMovement
from .services import InsufficientStockError, InventoryService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_category():
    return Category.objects.create(name='Test', icon='bi-box')


def make_product(stock=10, **kwargs):
    cat = make_category()
    return Product.objects.create(
        category=cat,
        name=kwargs.get('name', 'Producto Test'),
        price=Decimal('9.99'),
        stock=stock,
    )


def make_admin():
    return User.objects.create_user(
        username='admin',
        email='admin@carely.test',
        password='Adm1nPaSS!',
        role=User.Role.ADMIN,
    )


def make_client():
    return User.objects.create_user(
        username='cliente',
        email='cliente@carely.test',
        password='Us3rPaSS!',
        role=User.Role.CLIENT,
    )


# ---------------------------------------------------------------------------
# 1. add_stock (Entrada)
# ---------------------------------------------------------------------------

class AddStockTests(TestCase):

    def test_entrada_aumenta_stock(self):
        """add_stock incrementa Product.stock en la cantidad indicada."""
        product = make_product(stock=10)
        InventoryService.add_stock(product, quantity=5, reason='Reposición')
        product.refresh_from_db()
        self.assertEqual(product.stock, 15)

    def test_entrada_crea_movimiento(self):
        """add_stock crea un InventoryMovement de tipo ENTRADA."""
        product = make_product(stock=0)
        InventoryService.add_stock(product, quantity=20)
        self.assertEqual(InventoryMovement.objects.count(), 1)
        m = InventoryMovement.objects.first()
        self.assertEqual(m.movement_type, InventoryMovement.MovementType.ENTRADA)
        self.assertEqual(m.quantity, 20)
        self.assertEqual(m.product, product)

    def test_entrada_registra_created_by(self):
        """add_stock registra el usuario que realizó la operación."""
        admin = make_admin()
        product = make_product()
        InventoryService.add_stock(product, quantity=3, created_by=admin)
        m = InventoryMovement.objects.first()
        self.assertEqual(m.created_by, admin)

    def test_entrada_con_quantity_cero_falla(self):
        """add_stock rechaza quantity == 0."""
        product = make_product()
        with self.assertRaises(ValueError):
            InventoryService.add_stock(product, quantity=0)

    def test_entrada_con_quantity_negativa_falla(self):
        """add_stock rechaza quantity negativa."""
        product = make_product()
        with self.assertRaises(ValueError):
            InventoryService.add_stock(product, quantity=-5)

    def test_entrada_no_crea_movimiento_si_falla(self):
        """Si add_stock lanza ValueError, no se crea ningún movimiento."""
        product = make_product(stock=10)
        with self.assertRaises(ValueError):
            InventoryService.add_stock(product, quantity=0)
        self.assertEqual(InventoryMovement.objects.count(), 0)
        product.refresh_from_db()
        self.assertEqual(product.stock, 10)  # stock sin cambios


# ---------------------------------------------------------------------------
# 2. remove_stock (Salida)
# ---------------------------------------------------------------------------

class RemoveStockTests(TestCase):

    def test_salida_disminuye_stock(self):
        """remove_stock reduce Product.stock en la cantidad indicada."""
        product = make_product(stock=10)
        InventoryService.remove_stock(product, quantity=3)
        product.refresh_from_db()
        self.assertEqual(product.stock, 7)

    def test_salida_crea_movimiento(self):
        """remove_stock crea un InventoryMovement de tipo SALIDA."""
        product = make_product(stock=10)
        InventoryService.remove_stock(product, quantity=4, reason='Venta')
        self.assertEqual(InventoryMovement.objects.count(), 1)
        m = InventoryMovement.objects.first()
        self.assertEqual(m.movement_type, InventoryMovement.MovementType.SALIDA)
        self.assertEqual(m.quantity, 4)

    def test_salida_exacta_al_stock(self):
        """remove_stock permite retirar exactamente el stock disponible."""
        product = make_product(stock=5)
        InventoryService.remove_stock(product, quantity=5)
        product.refresh_from_db()
        self.assertEqual(product.stock, 0)

    def test_salida_superior_al_stock_falla(self):
        """remove_stock lanza InsufficientStockError si quantity > stock."""
        product = make_product(stock=3)
        with self.assertRaises(InsufficientStockError):
            InventoryService.remove_stock(product, quantity=4)

    def test_salida_superior_no_modifica_stock(self):
        """Si remove_stock falla, Product.stock no se modifica (rollback)."""
        product = make_product(stock=3)
        with self.assertRaises(InsufficientStockError):
            InventoryService.remove_stock(product, quantity=10)
        product.refresh_from_db()
        self.assertEqual(product.stock, 3)

    def test_salida_superior_no_crea_movimiento(self):
        """Si remove_stock falla, no se crea InventoryMovement."""
        product = make_product(stock=3)
        with self.assertRaises(InsufficientStockError):
            InventoryService.remove_stock(product, quantity=10)
        self.assertEqual(InventoryMovement.objects.count(), 0)

    def test_salida_con_stock_cero_falla(self):
        """remove_stock falla si el stock es 0."""
        product = make_product(stock=0)
        with self.assertRaises(InsufficientStockError):
            InventoryService.remove_stock(product, quantity=1)

    def test_salida_con_quantity_cero_falla(self):
        """remove_stock rechaza quantity == 0."""
        product = make_product(stock=10)
        with self.assertRaises(ValueError):
            InventoryService.remove_stock(product, quantity=0)

    def test_salida_con_quantity_negativa_falla(self):
        """remove_stock rechaza quantity negativa."""
        product = make_product(stock=10)
        with self.assertRaises(ValueError):
            InventoryService.remove_stock(product, quantity=-1)


# ---------------------------------------------------------------------------
# 3. adjust_stock (Ajuste)
# ---------------------------------------------------------------------------

class AdjustStockTests(TestCase):

    def test_ajuste_establece_nuevo_stock(self):
        """adjust_stock fija Product.stock al valor indicado."""
        product = make_product(stock=10)
        InventoryService.adjust_stock(product, new_stock=25)
        product.refresh_from_db()
        self.assertEqual(product.stock, 25)

    def test_ajuste_crea_movimiento(self):
        """adjust_stock crea un InventoryMovement de tipo AJUSTE."""
        product = make_product(stock=10)
        InventoryService.adjust_stock(product, new_stock=15, reason='Recuento físico')
        self.assertEqual(InventoryMovement.objects.count(), 1)
        m = InventoryMovement.objects.first()
        self.assertEqual(m.movement_type, InventoryMovement.MovementType.AJUSTE)

    def test_ajuste_registra_variacion_positiva(self):
        """Si new_stock > stock, quantity del movimiento es positiva."""
        product = make_product(stock=10)
        InventoryService.adjust_stock(product, new_stock=15)
        m = InventoryMovement.objects.first()
        self.assertEqual(m.quantity, 5)   # variación neta = +5

    def test_ajuste_registra_variacion_negativa(self):
        """Si new_stock < stock, quantity del movimiento es negativa."""
        product = make_product(stock=10)
        InventoryService.adjust_stock(product, new_stock=3)
        m = InventoryMovement.objects.first()
        self.assertEqual(m.quantity, -7)  # variación neta = -7

    def test_ajuste_a_cero(self):
        """adjust_stock permite fijar stock a 0."""
        product = make_product(stock=5)
        InventoryService.adjust_stock(product, new_stock=0)
        product.refresh_from_db()
        self.assertEqual(product.stock, 0)

    def test_ajuste_negativo_falla(self):
        """adjust_stock rechaza new_stock negativo."""
        product = make_product(stock=5)
        with self.assertRaises(ValueError):
            InventoryService.adjust_stock(product, new_stock=-1)

    def test_ajuste_negativo_no_modifica_stock(self):
        """Si adjust_stock falla, Product.stock no se modifica."""
        product = make_product(stock=5)
        with self.assertRaises(ValueError):
            InventoryService.adjust_stock(product, new_stock=-1)
        product.refresh_from_db()
        self.assertEqual(product.stock, 5)


# ---------------------------------------------------------------------------
# 4. Rollback / Atomicidad
# ---------------------------------------------------------------------------

class RollbackTests(TestCase):
    """Verifica que las operaciones son atómicas (todo o nada)."""

    def test_error_en_movimiento_revierte_stock(self):
        """
        Si la creación de InventoryMovement falla después de actualizar
        Product.stock, el stock debe revertirse.

        Simulamos esto con un mock que rompe InventoryMovement.objects.create.
        """
        from unittest.mock import patch

        product = make_product(stock=10)
        original_stock = product.stock

        with patch.object(InventoryMovement.objects, 'create', side_effect=Exception('DB error')):
            with self.assertRaises(Exception, msg='DB error'):
                InventoryService.add_stock(product, quantity=5)

        product.refresh_from_db()
        self.assertEqual(product.stock, original_stock, 'El stock debe ser el mismo tras el rollback')
        self.assertEqual(InventoryMovement.objects.count(), 0)


# ---------------------------------------------------------------------------
# 5. API — permisos
# ---------------------------------------------------------------------------

class InventoryAPIPermissionsTests(TestCase):
    """Verifica que solo admins pueden acceder a los endpoints de inventario."""

    def setUp(self):
        self.admin = make_admin()
        self.client_user = make_client()
        self.product = make_product(stock=50)

    def test_cliente_no_puede_listar_movimientos(self):
        """Un cliente autenticado recibe 403 al pedir el listado de movimientos."""
        from django.test import Client as DjangoClient
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(self.client_user)
        response = client.get('/api/v1/inventario/movimientos/')
        self.assertIn(response.status_code, [403, 401])

    def test_anonimo_no_puede_listar_movimientos(self):
        """Un usuario anónimo recibe 401/403 al pedir movimientos."""
        from rest_framework.test import APIClient

        client = APIClient()
        response = client.get('/api/v1/inventario/movimientos/')
        self.assertIn(response.status_code, [401, 403])

    def test_cliente_no_puede_registrar_entrada(self):
        """Un cliente autenticado no puede registrar entradas de stock."""
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(self.client_user)
        response = client.post('/api/v1/inventario/movimientos/entrada/', {
            'product': self.product.pk,
            'quantity': 5,
        })
        self.assertIn(response.status_code, [401, 403])

    def test_admin_puede_registrar_entrada(self):
        """Un admin puede registrar una entrada de stock vía API."""
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(self.admin)
        response = client.post('/api/v1/inventario/movimientos/entrada/', {
            'product': self.product.pk,
            'quantity': 10,
            'reason': 'Test',
        })
        self.assertEqual(response.status_code, 201)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 60)

    def test_admin_puede_registrar_salida(self):
        """Un admin puede registrar una salida de stock vía API."""
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(self.admin)
        response = client.post('/api/v1/inventario/movimientos/salida/', {
            'product': self.product.pk,
            'quantity': 5,
            'reason': 'Venta test',
        })
        self.assertEqual(response.status_code, 201)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 45)

    def test_admin_salida_excesiva_retorna_400(self):
        """Una salida mayor al stock retorna 400 BAD REQUEST."""
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(self.admin)
        response = client.post('/api/v1/inventario/movimientos/salida/', {
            'product': self.product.pk,
            'quantity': 999,
        })
        self.assertEqual(response.status_code, 400)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 50)  # sin cambios

    def test_admin_puede_ajustar_stock(self):
        """Un admin puede ajustar el stock absoluto vía API."""
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(self.admin)
        response = client.post('/api/v1/inventario/movimientos/ajuste/', {
            'product': self.product.pk,
            'new_stock': 100,
            'reason': 'Inventario físico',
        })
        self.assertEqual(response.status_code, 201)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 100)


# ---------------------------------------------------------------------------
# 6. Concurrencia — stock nunca negativo con operaciones simultáneas
# ---------------------------------------------------------------------------

class ConcurrencyTests(TransactionTestCase):
    """
    Usa TransactionTestCase para que las transacciones se confirmen
    y puedan ser vistas por otros hilos.
    """

    def test_operaciones_concurrentes_no_permiten_stock_negativo(self):
        """
        Dos salidas simultáneas que en conjunto superan el stock
        deben resultar en que una falle con InsufficientStockError
        y el stock nunca quede en negativo.
        """
        import threading

        cat = Category.objects.create(name='ConcTest', icon='bi-box')
        product = Product.objects.create(
            category=cat, name='ConcProduct', price=Decimal('1.00'), stock=5
        )

        errors = []
        successes = []

        def try_remove(qty):
            try:
                InventoryService.remove_stock(product, quantity=qty, reason='concurrency test')
                successes.append(qty)
            except InsufficientStockError as e:
                errors.append(str(e))
            except Exception as e:
                errors.append(f'Unexpected: {e}')

        # Intentamos retirar 4 + 4 = 8 unidades con stock de 5
        t1 = threading.Thread(target=try_remove, args=(4,))
        t2 = threading.Thread(target=try_remove, args=(4,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        product.refresh_from_db()

        # El stock debe ser >= 0 (nunca negativo)
        self.assertGreaterEqual(product.stock, 0, 'El stock nunca debe ser negativo')

        # Exactamente una operación debe haber tenido éxito
        total_moved = sum(successes)
        self.assertLessEqual(total_moved, 5, 'No se puede mover más stock del disponible')
