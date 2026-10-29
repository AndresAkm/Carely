import io
from decimal import Decimal
from uuid import uuid4

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from PIL import Image, ImageDraw
from rest_framework import status
from rest_framework.test import APITestCase

from apps.catalog.forms import ProductForm
from apps.catalog.models import Category, Product
from apps.catalog.services import nombre_sin_fondo, quitar_fondo_blanco
from apps.inventory.models import InventoryMovement
from apps.users.models import User


class CatalogWebFilterTests(TestCase):
    def setUp(self):
        self.cat1 = Category.objects.create(name='Cuidado facial', slug='cuidado-facial', icon='bi-person', order=1)
        self.cat2 = Category.objects.create(name='Cuidado corporal', slug='cuidado-corporal', icon='bi-body-text', order=2)
        self.p1 = Product.objects.create(category=self.cat1, name='Crema hidratante', slug='crema-hidratante', price=Decimal('50000.00'), stock=10, is_active=True, featured=True, brand='Carely')
        self.p2 = Product.objects.create(category=self.cat1, name='Serum vitamina C', slug='serum-vitamina-c', price=Decimal('80000.00'), stock=0, is_active=True, brand='Acme')
        self.p3 = Product.objects.create(category=self.cat2, name='Jabon corporal', slug='jabon-corporal', price=Decimal('30000.00'), stock=5, is_active=True, brand='Carely')
        self.url = reverse('catalog:home')

    def test_filter_by_category_slug(self):
        resp = self.client.get(self.url + '?category=cuidado-facial')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Crema hidratante')
        self.assertContains(resp, 'Serum vitamina C')
        self.assertNotContains(resp, 'Jabon corporal')

    def test_filter_by_brand(self):
        resp = self.client.get(self.url + '?brand=Carely')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Crema hidratante')
        self.assertContains(resp, 'Jabon corporal')
        self.assertNotContains(resp, 'Serum vitamina C')

    def test_filter_brand_case_insensitive(self):
        resp = self.client.get(self.url + '?brand=carely')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Crema hidratante')
        self.assertContains(resp, 'Jabon corporal')

    def test_filter_price_range(self):
        resp = self.client.get(self.url + '?min_price=40000&max_price=60000')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Crema hidratante')
        self.assertNotContains(resp, 'Serum vitamina C')
        self.assertNotContains(resp, 'Jabon corporal')

    def test_filter_price_gte_only(self):
        resp = self.client.get(self.url + '?min_price=60000')
        self.assertContains(resp, 'Serum vitamina C')
        self.assertNotContains(resp, 'Crema hidratante')
        self.assertNotContains(resp, 'Jabon corporal')

    def test_filter_price_lte_only(self):
        resp = self.client.get(self.url + '?max_price=60000')
        self.assertContains(resp, 'Crema hidratante')
        self.assertContains(resp, 'Jabon corporal')
        self.assertNotContains(resp, 'Serum vitamina C')

    def test_filter_in_stock(self):
        resp = self.client.get(self.url + '?in_stock=true')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Crema hidratante')
        self.assertContains(resp, 'Jabon corporal')
        self.assertNotContains(resp, 'Serum vitamina C')  # stock == 0

    def test_filter_featured(self):
        resp = self.client.get(self.url + '?featured=true')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Crema hidratante')
        self.assertNotContains(resp, 'Serum vitamina C')
        self.assertNotContains(resp, 'Jabon corporal')

    def test_precio_con_descuento_se_muestra_en_catalogo_y_detalle(self):
        self.p1.discount_percent = Decimal('20.00')
        self.p1.save(update_fields=['discount_percent'])

        catalog = self.client.get(self.url)
        detail = self.client.get(
            reverse('catalog:product_detail', args=[self.p1.slug]),
        )

        self.assertContains(catalog, 'product-card__discount-badge">-20%')
        self.assertContains(catalog, 'product-card__price--final">COP 40000')
        self.assertContains(detail, 'COP 40000')

    def test_search_q_name(self):
        resp = self.client.get(self.url + '?q=crema')
        self.assertContains(resp, 'Crema hidratante')

    def test_search_q_description(self):
        p = Product.objects.get(slug='jabon-corporal')
        p.description = 'jabón con aroma fresco'
        p.save()
        resp = self.client.get(self.url + '?q=aroma')
        self.assertContains(resp, 'Jabon corporal')

    def test_ordering_by_price_asc(self):
        resp = self.client.get(self.url + '?ordering=price')
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        pos_jabon = html.find('Jabon corporal')
        pos_crema = html.find('Crema hidratante')
        pos_serum = html.find('Serum vitamina C')
        self.assertTrue(pos_jabon < pos_crema < pos_serum)

    def test_ordering_by_price_desc(self):
        resp = self.client.get(self.url + '?ordering=-price')
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        pos_serum = html.find('Serum vitamina C')
        pos_crema = html.find('Crema hidratante')
        pos_jabon = html.find('Jabon corporal')
        self.assertTrue(pos_serum < pos_crema < pos_jabon)

    def test_pagination_preserves_filters(self):
        for i in range(12):
            Product.objects.create(category=self.cat1, name=f'Extra {i}', slug=f'extra-{i}', price=Decimal('20000.00'), stock=1, is_active=True, brand='Carely')
        resp = self.client.get(self.url + '?brand=Carely&page=2')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'brand=Carely')

    def test_inactive_category_not_listed(self):
        self.cat1.is_active = False
        self.cat1.save()
        resp = self.client.get(self.url + '?category=cuidado-facial')
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'Crema hidratante')
        self.assertNotContains(resp, 'Serum vitamina C')

    def test_inactive_product_not_listed(self):
        self.p1.is_active = False
        self.p1.save()
        resp = self.client.get(self.url)
        self.assertNotContains(resp, 'Crema hidratante')


class CatalogAPIFilterTests(APITestCase):
    def setUp(self):
        self.cat = Category.objects.create(name='Cuidado facial', slug='cuidado-facial', icon='bi-person')
        self.p1 = Product.objects.create(category=self.cat, name='Crema', slug='crema', price=Decimal('50000.00'), stock=5, is_active=True, featured=True, brand='Carely')
        self.p2 = Product.objects.create(category=self.cat, name='Serum', slug='serum', price=Decimal('80000.00'), stock=0, is_active=True, brand='Acme')
        self.url = reverse('productos-list')

    def _results(self, data):
        if isinstance(data, dict) and 'results' in data:
            return data['results']
        return data

    def test_api_list_paginates(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('results', data)
        self.assertIn('count', data)
        self.assertIn('next', data)
        self.assertIn('previous', data)

    def test_api_filters_by_brand(self):
        resp = self.client.get(self.url + '?brand=Carely')
        self.assertEqual(resp.status_code, 200)
        results = self._results(resp.json())
        names = [r['name'] for r in results]
        self.assertIn('Crema', names)
        self.assertNotIn('Serum', names)

    def test_api_brand_case_insensitive(self):
        resp = self.client.get(self.url + '?brand=carely')
        self.assertEqual(resp.status_code, 200)
        results = self._results(resp.json())
        self.assertTrue(any(r['name'] == 'Crema' for r in results))

    def test_api_filter_category_slug(self):
        resp = self.client.get(self.url + '?category=cuidado-facial')
        self.assertEqual(resp.status_code, 200)
        results = self._results(resp.json())
        self.assertEqual(len(results), 2)

    def test_api_filter_price_range(self):
        resp = self.client.get(self.url + '?min_price=60000&max_price=90000')
        self.assertEqual(resp.status_code, 200)
        results = self._results(resp.json())
        self.assertTrue(all(60000 <= Decimal(str(r['price'])) <= 90000 for r in results))

    def test_api_filter_featured(self):
        resp = self.client.get(self.url + '?featured=true')
        self.assertEqual(resp.status_code, 200)
        results = self._results(resp.json())
        self.assertTrue(all(r['featured'] for r in results))

    def test_api_filter_in_stock(self):
        resp = self.client.get(self.url + '?in_stock=true')
        self.assertEqual(resp.status_code, 200)
        results = self._results(resp.json())
        self.assertTrue(all(r['stock'] > 0 for r in results))

    def test_api_search_q(self):
        self.p2.description = 'suero iluminador'
        self.p2.save()
        resp = self.client.get(self.url + '?q=iluminador')
        self.assertEqual(resp.status_code, 200)
        results = self._results(resp.json())
        names = [r['name'] for r in results]
        self.assertIn('Serum', names)

    def test_api_ordering_price_desc(self):
        resp = self.client.get(self.url + '?ordering=-price')
        self.assertEqual(resp.status_code, 200)
        results = self._results(resp.json())
        prices = [Decimal(str(r['price'])) for r in results]
        self.assertEqual(prices, sorted(prices, reverse=True))

    def test_api_anonymous_sees_only_active(self):
        self.p2.is_active = False
        self.p2.save()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        results = self._results(resp.json())
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['name'], 'Crema')

    def test_api_inactive_category_filtered(self):
        self.cat.is_active = False
        self.cat.save()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        results = self._results(resp.json())
        self.assertEqual(len(results), 0)


class CargarCatalogoCommandTests(TestCase):
    def setUp(self):
        self.generica = Category.objects.create(
            name='Maquillaje', slug='maquillaje', icon='bi-palette', order=3,
        )
        self.producto_generico = Product.objects.create(
            category=self.generica,
            name='Labial Mate de Larga Duración',
            slug='labial-mate-de-larga-duracion',
            price=Decimal('159.00'),
            stock=25,
        )

    def test_reemplaza_el_catalogo_generico(self):
        call_command('cargar_catalogo', verbosity=0)

        self.assertEqual(Category.objects.count(), 6)
        self.assertEqual(Product.objects.count(), 17)
        self.assertFalse(Category.objects.filter(slug='maquillaje').exists())
        self.assertFalse(
            Product.objects.filter(slug='labial-mate-de-larga-duracion').exists()
        )

    def test_asigna_imagen_marca_y_precio(self):
        call_command('cargar_catalogo', verbosity=0)

        protector = Product.objects.get(
            slug='anthelios-uvmune-400-anti-manchas-fps50-x50-ml',
        )
        self.assertEqual(protector.price, Decimal('143900.00'))
        self.assertEqual(protector.brand, 'La Roche-Posay')
        self.assertEqual(
            protector.image.name,
            'products/sun-protect-anthelios-400-la-roche-posay-sin-fondo.webp',
        )
        self.assertTrue(
            Category.objects.get(slug='proteccion-solar').image.name.endswith(
                'categories/category-sun-protect.jpg'
            )
        )

    def test_es_idempotente(self):
        call_command('cargar_catalogo', verbosity=0)
        call_command('cargar_catalogo', verbosity=0)

        self.assertEqual(Category.objects.count(), 6)
        self.assertEqual(Product.objects.count(), 17)

    def test_producto_con_historial_se_desactiva_en_lugar_de_borrarse(self):
        InventoryMovement.objects.create(
            product=self.producto_generico,
            quantity=5,
            movement_type=InventoryMovement.MovementType.SALIDA,
        )

        call_command('cargar_catalogo', verbosity=0)

        producto = Product.objects.get(slug='labial-mate-de-larga-duracion')
        self.assertFalse(producto.is_active)
        self.assertEqual(producto.stock, 0)
        # Maquillaje sigue existiendo porque protege al producto con historial.
        self.assertFalse(Category.objects.get(slug='maquillaje').is_active)


class CatalogDashboardCRUDTests(TestCase):
    """CRUD de productos y categorías desde el panel (solo administradores)."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin@carely.test',
            email='admin@carely.test',
            password='pass12345',
            role=User.Role.ADMIN,
            is_staff=True,
        )
        self.category = Category.objects.create(
            name='Base', slug='base', icon='bi-box',
        )

    def test_cliente_no_entra_al_panel(self):
        cliente = User.objects.create_user(
            username='cliente@carely.test',
            email='cliente@carely.test',
            password='pass12345',
            role=User.Role.CLIENT,
        )
        self.client.force_login(cliente)
        response = self.client.get(reverse('dashboard:product_list'))
        self.assertRedirects(response, reverse('core:home'))

    def test_crear_producto(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('dashboard:product_create'), {
            'name': 'Producto Dashboard',
            'price': '12000.00',
            'category': self.category.pk,
            'stock': 5,
            'brand': 'Carely',
            'discount_percent': '0',
        })
        self.assertRedirects(response, reverse('dashboard:product_list'))
        self.assertTrue(Product.objects.filter(slug='producto-dashboard').exists())

    def test_crear_producto_con_imagen_le_quita_el_fondo(self):
        self.client.force_login(self.admin)
        nombre = f'dashboard-{uuid4().hex}.jpg'
        response = self.client.post(reverse('dashboard:product_create'), {
            'name': 'Producto con imagen',
            'price': '12000.00',
            'category': self.category.pk,
            'stock': 5,
            'brand': 'Carely',
            'discount_percent': '0',
            'image': SimpleUploadedFile(
                nombre,
                _imagen_de_prueba('JPEG'),
                content_type='image/jpeg',
            ),
        })

        self.assertRedirects(response, reverse('dashboard:product_list'))
        producto = Product.objects.get(slug='producto-con-imagen')
        self.assertEqual(
            producto.image.name,
            f'products/{nombre.removesuffix(".jpg")}-sin-fondo.webp',
        )

    def test_editar_producto(self):
        producto = Product.objects.create(
            category=self.category, name='Editame', slug='editame',
            price=Decimal('1000.00'),
        )
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('dashboard:product_update', args=[producto.pk]),
            {
                'name': 'Editado',
                'price': '2000.00',
                'category': self.category.pk,
                'stock': 0,
                'discount_percent': '0',
            },
        )
        self.assertRedirects(response, reverse('dashboard:product_list'))
        producto.refresh_from_db()
        self.assertEqual(producto.name, 'Editado')
        self.assertEqual(producto.price, Decimal('2000.00'))

    def test_eliminar_producto_sin_historial(self):
        producto = Product.objects.create(
            category=self.category, name='Borrame', slug='borrame',
            price=Decimal('1000.00'),
        )
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('dashboard:product_delete', args=[producto.pk]),
        )
        self.assertRedirects(response, reverse('dashboard:product_list'))
        self.assertFalse(Product.objects.filter(pk=producto.pk).exists())

    def test_crear_categoria(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('dashboard:category_create'), {
            'name': 'Nueva Categoria',
            'icon': 'bi-star',
            'order': 5,
        })
        self.assertRedirects(response, reverse('dashboard:category_list'))
        self.assertTrue(Category.objects.filter(slug='nueva-categoria').exists())

    def test_no_elimina_categoria_con_productos(self):
        Product.objects.create(
            category=self.category, name='Protegido', slug='protegido',
            price=Decimal('1000.00'),
        )
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('dashboard:category_delete', args=[self.category.pk]),
        )
        self.assertRedirects(response, reverse('dashboard:category_list'))
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())


class CatalogDeletionRulesTests(TestCase):
    """Qué se puede eliminar desde el panel y qué protege el historial.

    Un producto inactivo NO es eliminable por estar inactivo: se bloquea si
    tiene pedidos o movimientos de inventario. Una categoría se bloquea mientras
    tenga cualquier producto, activo o no.
    """

    def setUp(self):
        from apps.inventory.services import InventoryService

        self.admin = User.objects.create_user(
            username='admin-borrado@carely.test', email='admin-borrado@carely.test',
            password='pass12345', role=User.Role.ADMIN, is_staff=True,
        )
        self.client.force_login(self.admin)
        self.inventory = InventoryService
        self.categoria = Category.objects.create(name='Cuidado facial', slug='cuidado-facial', icon='bi-person')

    def producto(self, nombre, activo=True, categoria=None):
        return Product.objects.create(
            category=categoria or self.categoria, name=nombre, slug=nombre.lower().replace(' ', '-'),
            price=Decimal('10000.00'), is_active=activo,
        )

    def test_producto_inactivo_sin_historial_se_elimina(self):
        p = self.producto('Crema vieja', activo=False)
        self.client.post(reverse('dashboard:product_delete', args=[p.pk]))
        self.assertFalse(Product.objects.filter(pk=p.pk).exists())

    def test_producto_activo_sin_historial_se_elimina(self):
        p = self.producto('Crema nueva', activo=True)
        self.client.post(reverse('dashboard:product_delete', args=[p.pk]))
        self.assertFalse(Product.objects.filter(pk=p.pk).exists())

    def test_producto_inactivo_con_pedido_no_se_elimina(self):
        from apps.orders.models import Order, OrderItem

        p = self.producto('Serum vendido', activo=False)
        pedido = Order.objects.create(user=self.admin, total=Decimal('10000.00'), shipping_address='x')
        OrderItem.objects.create(
            order=pedido, product=p, product_name=p.name, quantity=1, unit_price=Decimal('10000.00'),
        )
        response = self.client.post(reverse('dashboard:product_delete', args=[p.pk]), follow=True)
        self.assertTrue(Product.objects.filter(pk=p.pk).exists())
        self.assertContains(response, 'tiene pedidos o movimientos de inventario')
        self.assertContains(response, 'Desactívalo')

    def test_producto_con_movimiento_de_inventario_no_se_elimina(self):
        p = self.producto('Tonico con stock', activo=False)
        self.inventory.add_stock(product=p, quantity=5, reason='carga inicial')
        self.client.post(reverse('dashboard:product_delete', args=[p.pk]))
        self.assertTrue(Product.objects.filter(pk=p.pk).exists())

    def test_categoria_vacia_se_elimina(self):
        vacia = Category.objects.create(name='Vacia', slug='vacia', icon='bi-x')
        self.client.post(reverse('dashboard:category_delete', args=[vacia.pk]))
        self.assertFalse(Category.objects.filter(pk=vacia.pk).exists())

    def test_categoria_con_producto_inactivo_no_se_elimina(self):
        # Aunque el producto esté inactivo y sin historial, la categoría sigue
        # protegida: el producto sí se podría borrar antes que la categoría.
        self.producto('Inactivo en categoria', activo=False)
        self.client.post(reverse('dashboard:category_delete', args=[self.categoria.pk]))
        self.assertTrue(Category.objects.filter(pk=self.categoria.pk).exists())

    def test_categoria_bloqueada_explica_como_liberarla(self):
        self.producto('Inactivo en categoria', activo=False)
        response = self.client.post(reverse('dashboard:category_delete', args=[self.categoria.pk]), follow=True)
        self.assertContains(response, 'activos o inactivos')
        self.assertContains(response, 'Cámbialos a otra categoría')

    def test_categoria_se_elimina_cuando_ya_no_tiene_productos(self):
        p = self.producto('Ultimo producto', activo=False)
        p.delete()
        self.client.post(reverse('dashboard:category_delete', args=[self.categoria.pk]))
        self.assertFalse(Category.objects.filter(pk=self.categoria.pk).exists())

    def test_pantalla_de_confirmacion_de_categoria_no_promete_borrar_productos(self):
        # El texto anterior decía que se borraban "sus productos asociados", y
        # el modelo lo impide: la pantalla debe decir lo que realmente pasa.
        response = self.client.get(reverse('dashboard:category_delete', args=[self.categoria.pk]))
        self.assertNotContains(response, 'sus productos asociados')


def _imagen_de_prueba(formato='PNG', fondo=(255, 255, 255)):
    imagen = Image.new('RGB', (120, 120), fondo)
    ImageDraw.Draw(imagen).rectangle((30, 30, 90, 90), fill=(200, 40, 60))
    buffer = io.BytesIO()
    imagen.save(buffer, format=formato)
    return buffer.getvalue()


class QuitarFondoBlancoTests(SimpleTestCase):
    def test_esquinas_transparentes_y_centro_opaco(self):
        resultado = quitar_fondo_blanco(_imagen_de_prueba())

        self.assertIsNotNone(resultado)
        salida, formato = resultado
        self.assertEqual(formato, 'WEBP')
        imagen = Image.open(io.BytesIO(salida)).convert('RGBA')
        self.assertEqual(imagen.getpixel((0, 0))[3], 0)
        self.assertEqual(imagen.getpixel((60, 60))[3], 255)

    def test_jpeg_se_convierte_a_webp(self):
        resultado = quitar_fondo_blanco(_imagen_de_prueba('JPEG'))

        self.assertIsNotNone(resultado)
        salida, formato = resultado
        self.assertEqual(formato, 'WEBP')
        self.assertEqual(salida[:4], b'RIFF')
        self.assertEqual(salida[8:12], b'WEBP')

    def test_png_se_convierte_a_webp(self):
        resultado = quitar_fondo_blanco(_imagen_de_prueba('PNG'))

        self.assertIsNotNone(resultado)
        _, formato = resultado
        self.assertEqual(formato, 'WEBP')

    def test_fondo_de_color_no_se_procesa(self):
        self.assertIsNone(quitar_fondo_blanco(_imagen_de_prueba(fondo=(20, 100, 200))))

    def test_imagen_ya_transparente_no_se_reprocesa(self):
        imagen = Image.new('RGBA', (120, 120), (255, 255, 255, 0))
        ImageDraw.Draw(imagen).rectangle((30, 30, 90, 90), fill=(200, 40, 60, 255))
        buffer = io.BytesIO()
        imagen.save(buffer, format='PNG')

        self.assertIsNone(quitar_fondo_blanco(buffer.getvalue()))


class QuitarFondoImagenesCommandTests(TestCase):
    def setUp(self):
        self.categoria = Category.objects.create(
            name='Cuidado de prueba', slug='cuidado-de-prueba', icon='bi-x',
        )
        self.token = uuid4().hex

    def _crear_producto(self, nombre, contenido):
        nombre = f'products/{nombre}-{self.token}.jpg'
        guardado = default_storage.save(nombre, ContentFile(contenido))
        producto = Product.objects.create(
            category=self.categoria,
            name=f'Producto {nombre}',
            slug=f'producto-{uuid4().hex}',
            price=Decimal('10000.00'),
            stock=1,
            image=guardado,
        )
        return producto, guardado

    def test_convierte_a_webp_y_actualiza_la_referencia(self):
        producto, original = self._crear_producto('producto', _imagen_de_prueba('JPEG'))

        call_command('quitar_fondo_imagenes', verbosity=0)

        producto.refresh_from_db()
        esperado = nombre_sin_fondo(original)
        self.assertEqual(producto.image.name, esperado)
        self.assertTrue(default_storage.exists(esperado))
        self.assertTrue(default_storage.exists(original))

        with default_storage.open(esperado, 'rb') as archivo:
            imagen = Image.open(archivo).convert('RGBA')
        self.assertEqual(imagen.getpixel((0, 0))[3], 0)
        self.assertEqual(imagen.getpixel((60, 60))[3], 255)

    def test_guarda_el_original_en_originales(self):
        _, original = self._crear_producto('con-respaldo', _imagen_de_prueba('JPEG'))
        contenido = default_storage.open(original, 'rb').read()

        call_command('quitar_fondo_imagenes', verbosity=0)

        respaldo = f'_originales/{original}'
        self.assertTrue(default_storage.exists(respaldo))
        with default_storage.open(respaldo, 'rb') as archivo:
            self.assertEqual(archivo.read(), contenido)

    def test_dry_run_no_escribe_ni_cambia_la_base(self):
        producto, original = self._crear_producto('sin-cambios', _imagen_de_prueba('JPEG'))

        call_command('quitar_fondo_imagenes', dry_run=True, verbosity=0)

        producto.refresh_from_db()
        self.assertEqual(producto.image.name, original)
        self.assertFalse(default_storage.exists(nombre_sin_fondo(original)))
        self.assertFalse(default_storage.exists(f'_originales/{original}'))

    def test_repara_referencia_faltante_y_procesa(self):
        contenido = _imagen_de_prueba('WEBP')
        real = f'products/neceser-{self.token}.webp'
        guardado = default_storage.save(real, ContentFile(contenido))
        producto = Product.objects.create(
            category=self.categoria,
            name='Neceser de prueba',
            slug=f'neceser-{self.token}',
            price=Decimal('10000.00'),
            stock=1,
            image=f'products/neceser-{self.token}_tttTBFB.webp',
        )

        call_command('quitar_fondo_imagenes', verbosity=0)

        producto.refresh_from_db()
        esperado = nombre_sin_fondo(guardado)
        self.assertEqual(producto.image.name, esperado)
        self.assertTrue(default_storage.exists(esperado))

    def test_no_repara_si_se_desactiva(self):
        contenido = _imagen_de_prueba('WEBP')
        real = f'products/neceser-{self.token}.webp'
        guardado = default_storage.save(real, ContentFile(contenido))
        faltante = f'products/neceser-{self.token}_tttTBFB.webp'
        producto = Product.objects.create(
            category=self.categoria,
            name='Neceser sin reparar',
            slug=f'neceser-sin-reparar-{self.token}',
            price=Decimal('10000.00'),
            stock=1,
            image=faltante,
        )

        call_command(
            'quitar_fondo_imagenes',
            no_reparar_referencias=True,
            verbosity=0,
        )

        producto.refresh_from_db()
        self.assertEqual(producto.image.name, faltante)
        self.assertFalse(default_storage.exists(nombre_sin_fondo(guardado)))

    def test_omite_imagenes_con_fondo_de_color(self):
        producto, original = self._crear_producto(
            'fondo-color', _imagen_de_prueba(fondo=(20, 100, 200)),
        )

        call_command('quitar_fondo_imagenes', verbosity=0)

        producto.refresh_from_db()
        self.assertEqual(producto.image.name, original)
        self.assertFalse(default_storage.exists(nombre_sin_fondo(original)))

    def test_dos_productos_que_comparten_imagen(self):
        contenido = _imagen_de_prueba('JPEG')
        nombre = f'products/compartida-{self.token}.jpg'
        guardado = default_storage.save(nombre, ContentFile(contenido))
        primero = Product.objects.create(
            category=self.categoria,
            name='Producto compartido 1',
            slug=f'compartido-1-{self.token}',
            price=Decimal('10000.00'),
            stock=1,
            image=guardado,
        )
        segundo = Product.objects.create(
            category=self.categoria,
            name='Producto compartido 2',
            slug=f'compartido-2-{self.token}',
            price=Decimal('10000.00'),
            stock=1,
            image=guardado,
        )

        call_command('quitar_fondo_imagenes', verbosity=0)

        esperado = nombre_sin_fondo(guardado)
        primero.refresh_from_db()
        segundo.refresh_from_db()
        self.assertEqual(primero.image.name, esperado)
        self.assertEqual(segundo.image.name, esperado)

    def test_respeta_el_limite(self):
        primero, original_primero = self._crear_producto('limite-1', _imagen_de_prueba('JPEG'))
        segundo, original_segundo = self._crear_producto('limite-2', _imagen_de_prueba('JPEG'))

        call_command('quitar_fondo_imagenes', limite=1, verbosity=0)

        primero.refresh_from_db()
        segundo.refresh_from_db()
        self.assertEqual(primero.image.name, nombre_sin_fondo(original_primero))
        self.assertEqual(segundo.image.name, original_segundo)


class ProductImagenAutomaticaTests(TestCase):
    def setUp(self):
        self.categoria = Category.objects.create(
            name='Fondo automático', slug='fondo-automatico', icon='bi-x',
        )

    def _crear_producto(self, contenido, formato='JPEG'):
        nombre = f'producto-{uuid4().hex}.jpg'
        imagen = SimpleUploadedFile(
            nombre,
            contenido,
            content_type=f'image/{formato.lower()}',
        )
        producto = Product.objects.create(
            category=self.categoria,
            name=f'Producto {nombre}',
            price=Decimal('10000.00'),
            stock=1,
            image=imagen,
        )
        return producto, nombre

    def test_al_crear_producto_con_imagen_le_quita_el_fondo(self):
        producto, nombre = self._crear_producto(_imagen_de_prueba('JPEG'))

        esperado = f'products/{nombre.removesuffix(".jpg")}-sin-fondo.webp'
        producto.refresh_from_db()
        self.assertEqual(producto.image.name, esperado)
        with producto.image.open('rb') as archivo:
            imagen = Image.open(archivo).convert('RGBA')
        self.assertEqual(imagen.getpixel((0, 0))[3], 0)
        self.assertEqual(imagen.getpixel((60, 60))[3], 255)

    def test_reguardar_no_reprocesa_la_imagen(self):
        producto, _ = self._crear_producto(_imagen_de_prueba('JPEG'))
        producto.refresh_from_db()
        esperado = producto.image.name

        producto.save()
        producto.refresh_from_db()

        self.assertEqual(producto.image.name, esperado)

    def test_imagen_con_fondo_de_color_se_conserva(self):
        producto, nombre = self._crear_producto(
            _imagen_de_prueba(fondo=(20, 100, 200)),
        )

        producto.refresh_from_db()
        self.assertEqual(producto.image.name, f'products/{nombre}')

    def test_categoria_no_se_procesa(self):
        nombre = f'categoria-{uuid4().hex}.jpg'
        categoria = Category.objects.create(
            name=f'Categoría {nombre}',
            slug=f'categoria-{uuid4().hex}',
            icon='bi-x',
            image=SimpleUploadedFile(
                nombre,
                _imagen_de_prueba('JPEG'),
                content_type='image/jpeg',
            ),
        )

        categoria.refresh_from_db()
        self.assertEqual(categoria.image.name, f'categories/{nombre}')

    def test_formulario_del_panel_tambien_lo_aplica(self):
        nombre = f'formulario-{uuid4().hex}.jpg'
        form = ProductForm(
            data={
                'category': self.categoria.pk,
                'name': 'Producto de formulario',
                'description': '',
                'price': '10000.00',
                'stock': '1',
                'brand': '',
                'discount_percent': '0',
            },
            files={
                'image': SimpleUploadedFile(
                    nombre,
                    _imagen_de_prueba('JPEG'),
                    content_type='image/jpeg',
                ),
            },
        )

        self.assertTrue(form.is_valid(), form.errors)
        producto = form.save()

        self.assertEqual(
            producto.image.name,
            f'products/{nombre.removesuffix(".jpg")}-sin-fondo.webp',
        )


class ProductImagenAPITests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin-imagenes@carely.test',
            email='admin-imagenes@carely.test',
            password='clave-de-prueba',
            role='admin',
        )
        self.client.force_authenticate(self.admin)
        self.categoria = Category.objects.create(
            name='Fondo API', slug='fondo-api', icon='bi-x',
        )

    def test_crear_producto_por_api_procesa_la_imagen(self):
        nombre = f'api-{uuid4().hex}.jpg'
        respuesta = self.client.post(
            reverse('productos-list'),
            {
                'category': self.categoria.pk,
                'name': 'Producto por API',
                'price': '10000.00',
                'stock': 1,
                'image': SimpleUploadedFile(
                    nombre,
                    _imagen_de_prueba('JPEG'),
                    content_type='image/jpeg',
                ),
            },
            format='multipart',
        )

        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED)
        self.assertIn('-sin-fondo.webp', respuesta.data['image'])
