from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.catalog.models import Category, Product
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