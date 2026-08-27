from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Address, User


def create_user(**kwargs):
    defaults = {
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'pass12345',
    }
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)


def create_address(user, **kwargs):
    defaults = {
        'recipient_name': 'Juan Perez',
        'address_line': 'Calle 10 # 20-30',
        'city': 'Medellín',
        'department': 'Antioquia',
    }
    defaults.update(kwargs)
    return Address.objects.create(user=user, **defaults)


class AddressModelTests(APITestCase):
    def test_create_address(self):
        user = create_user()
        addr = create_address(user)
        self.assertEqual(addr.user, user)
        self.assertEqual(addr.recipient_name, 'Juan Perez')
        self.assertTrue(addr.is_active)
        self.assertFalse(addr.is_default)

    def test_str(self):
        user = create_user()
        addr = create_address(user)
        self.assertIn('Juan Perez', str(addr))
        self.assertIn('Medellín', str(addr))

    def test_first_address_becomes_default_via_viewset(self):
        user = create_user()
        create_address(user)
        addr2 = create_address(user, recipient_name='Segunda')
        self.assertFalse(addr2.is_default)

    def test_default_address_clears_others(self):
        user = create_user()
        addr1 = create_address(user, is_default=True)
        addr2 = create_address(user, recipient_name='Segunda', is_default=True)
        addr1.refresh_from_db()
        self.assertFalse(addr1.is_default)
        self.assertTrue(addr2.is_default)

    def test_inactive_address_cannot_be_default(self):
        user = create_user()
        addr = create_address(user, is_active=False, is_default=True)
        addr.refresh_from_db()
        self.assertFalse(addr.is_default)

    def test_soft_delete(self):
        user = create_user()
        addr = create_address(user)
        addr.is_active = False
        addr.save(update_fields=['is_active'])
        addr.refresh_from_db()
        self.assertFalse(addr.is_active)
        self.assertTrue(Address.objects.filter(pk=addr.pk).exists())


class AddressAPICreateTests(APITestCase):
    def setUp(self):
        self.user = create_user()
        self.client.force_authenticate(self.user)
        self.url = reverse('direcciones-list')

    def test_create_address(self):
        data = {
            'recipient_name': 'Juan Perez',
            'phone': '3001234567',
            'address_line': 'Calle 10 # 20-30',
            'city': 'Medellín',
            'department': 'Antioquia',
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['user']['id'], self.user.pk)
        self.assertTrue(response.data['is_default'])

    def test_create_address_assigns_to_authenticated_user(self):
        data = {
            'recipient_name': 'Juan Perez',
            'address_line': 'Calle 10 # 20-30',
            'city': 'Medellín',
            'department': 'Antioquia',
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        addr = Address.objects.get(pk=response.data['id'])
        self.assertEqual(addr.user, self.user)

    def test_first_address_is_default(self):
        data = {
            'recipient_name': 'Primera',
            'address_line': 'Calle 10',
            'city': 'Bogotá',
            'department': 'Cundinamarca',
        }
        response = self.client.post(self.url, data, format='json')
        self.assertTrue(response.data['is_default'])

    def test_second_address_is_not_default(self):
        self.client.post(self.url, {
            'recipient_name': 'Primera',
            'address_line': 'Calle 10',
            'city': 'Bogotá',
            'department': 'Cundinamarca',
        }, format='json')
        data = {
            'recipient_name': 'Segunda',
            'address_line': 'Calle 20',
            'city': 'Cali',
            'department': 'Valle del Cauca',
        }
        response = self.client.post(self.url, data, format='json')
        self.assertFalse(response.data['is_default'])

    def test_create_address_requires_fields(self):
        response = self.client.post(self.url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_cannot_assign_other_user(self):
        other = create_user(username='other', email='other@example.com')
        data = {
            'recipient_name': 'Hack',
            'address_line': 'Calle X',
            'city': 'Bogotá',
            'department': 'Cundinamarca',
            'user': other.pk,
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        addr = Address.objects.get(pk=response.data['id'])
        self.assertEqual(addr.user, self.user)


class AddressAPIListTests(APITestCase):
    def setUp(self):
        self.user_a = create_user()
        self.user_b = create_user(username='userb', email='b@example.com')
        self.addr_a = create_address(self.user_a)
        self.addr_b = create_address(self.user_b, recipient_name='Direccion B')
        self.url = reverse('direcciones-list')

    def test_list_only_own_addresses(self):
        self.client.force_authenticate(self.user_a)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], self.addr_a.pk)

    def test_list_excludes_inactive(self):
        self.addr_a.is_active = False
        self.addr_a.save(update_fields=['is_active'])
        self.client.force_authenticate(self.user_a)
        response = self.client.get(self.url)
        self.assertEqual(len(response.data), 0)

    def test_unauthenticated_cannot_list(self):
        response = self.client.get(self.url)
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))


class AddressAPIDetailTests(APITestCase):
    def setUp(self):
        self.user = create_user()
        self.addr = create_address(self.user)
        self.url = reverse('direcciones-detail', args=[self.addr.pk])

    def test_retrieve_own_address(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.addr.pk)

    def test_cannot_retrieve_others_address(self):
        other = create_user(username='other', email='other@example.com')
        self.client.force_authenticate(other)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class AddressAPIUpdateTests(APITestCase):
    def setUp(self):
        self.user = create_user()
        self.addr = create_address(self.user)
        self.url = reverse('direcciones-detail', args=[self.addr.pk])

    def test_update_own_address(self):
        self.client.force_authenticate(self.user)
        data = {
            'recipient_name': 'Nuevo Nombre',
            'address_line': 'Nueva Calle',
            'city': 'Barranquilla',
            'department': 'Atlántico',
        }
        response = self.client.patch(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.addr.refresh_from_db()
        self.assertEqual(self.addr.recipient_name, 'Nuevo Nombre')

    def test_cannot_update_others_address(self):
        other = create_user(username='other', email='other@example.com')
        self.client.force_authenticate(other)
        data = {'recipient_name': 'Hacked'}
        response = self.client.patch(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_change_user_field(self):
        other = create_user(username='other', email='other@example.com')
        self.client.force_authenticate(self.user)
        data = {'user': other.pk}
        response = self.client.patch(self.url, data, format='json')
        self.addr.refresh_from_db()
        self.assertEqual(self.addr.user, self.user)


class AddressAPIDeleteTests(APITestCase):
    def setUp(self):
        self.user = create_user()
        self.addr = create_address(self.user)
        self.url = reverse('direcciones-detail', args=[self.addr.pk])

    def test_delete_is_soft_delete(self):
        self.client.force_authenticate(self.user)
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.addr.refresh_from_db()
        self.assertFalse(self.addr.is_active)
        self.assertTrue(Address.objects.filter(pk=self.addr.pk).exists())

    def test_deleted_address_not_in_list(self):
        self.client.force_authenticate(self.user)
        self.client.delete(self.url)
        response = self.client.get(reverse('direcciones-list'))
        self.assertEqual(len(response.data), 0)

    def test_cannot_delete_others_address(self):
        other = create_user(username='other', email='other@example.com')
        self.client.force_authenticate(other)
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_soft_delete_clears_default(self):
        self.addr.is_default = True
        self.addr.save(update_fields=['is_default'])
        self.client.force_authenticate(self.user)
        self.client.delete(self.url)
        self.addr.refresh_from_db()
        self.assertFalse(self.addr.is_default)


class AddressAPISetDefaultTests(APITestCase):
    def setUp(self):
        self.user = create_user()
        self.addr_a = create_address(self.user, is_default=True)
        self.addr_b = create_address(self.user, recipient_name='Segunda')

    def test_set_default(self):
        self.client.force_authenticate(self.user)
        url = reverse('direcciones-set-default', args=[self.addr_b.pk])
        response = self.client.patch(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.addr_a.refresh_from_db()
        self.addr_b.refresh_from_db()
        self.assertFalse(self.addr_a.is_default)
        self.assertTrue(self.addr_b.is_default)

    def test_set_default_others_address(self):
        other = create_user(username='other', email='other@example.com')
        other_addr = create_address(other)
        self.client.force_authenticate(other)
        url = reverse('direcciones-set-default', args=[other_addr.pk])
        response = self.client.patch(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        other_addr.refresh_from_db()
        self.assertTrue(other_addr.is_default)
        self.addr_a.refresh_from_db()
        self.assertTrue(self.addr_a.is_default)

    def test_cannot_set_inactive_as_default(self):
        self.addr_b.is_active = False
        self.addr_b.save(update_fields=['is_active'])
        self.client.force_authenticate(self.user)
        url = reverse('direcciones-set-default', args=[self.addr_b.pk])
        response = self.client.patch(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.addr_a.refresh_from_db()
        self.assertTrue(self.addr_a.is_default)

    def test_never_two_defaults(self):
        self.client.force_authenticate(self.user)
        url = reverse('direcciones-set-default', args=[self.addr_b.pk])
        self.client.patch(url, format='json')
        defaults = Address.objects.filter(user=self.user, is_active=True, is_default=True).count()
        self.assertEqual(defaults, 1)

    def test_set_default_own_address_only(self):
        other = create_user(username='other', email='other@example.com')
        other_addr = create_address(other, is_default=True)
        self.client.force_authenticate(self.user)
        url = reverse('direcciones-set-default', args=[other_addr.pk])
        response = self.client.patch(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class AddressSecurityTests(APITestCase):
    def setUp(self):
        self.user_a = create_user()
        self.user_b = create_user(username='userb', email='b@example.com')
        self.addr_b = create_address(self.user_b, recipient_name='Direccion B')

    def test_user_a_cannot_read_user_b_address(self):
        self.client.force_authenticate(self.user_a)
        url = reverse('direcciones-detail', args=[self.addr_b.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_a_cannot_update_user_b_address(self):
        self.client.force_authenticate(self.user_a)
        url = reverse('direcciones-detail', args=[self.addr_b.pk])
        response = self.client.patch(url, {'recipient_name': 'Hack'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_a_cannot_delete_user_b_address(self):
        self.client.force_authenticate(self.user_a)
        url = reverse('direcciones-detail', args=[self.addr_b.pk])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_a_cannot_set_default_user_b_address(self):
        self.client.force_authenticate(self.user_a)
        url = reverse('direcciones-set-default', args=[self.addr_b.pk])
        response = self.client.patch(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_cannot_access(self):
        url = reverse('direcciones-list')
        response = self.client.get(url)
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
