from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Address, City, Department, User


def create_user(**kwargs):
    defaults = {
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'pass12345',
    }
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)


_geo_counter = [0]


def create_geo(department_name='Antioquia', city_name='Medellín'):
    _geo_counter[0] += 1
    department = Department.objects.create(api_id=_geo_counter[0], name=department_name)
    city = City.objects.create(api_id=_geo_counter[0], name=city_name, department=department)
    return department, city


def create_address(user, **kwargs):
    department = kwargs.pop('department_obj', None)
    city = kwargs.pop('city_obj', None)
    if department is None or city is None:
        department, city = create_geo()
    defaults = {
        'recipient_name': 'Juan Perez',
        'address_line': 'Calle 10 # 20-30',
        'department': department,
        'city': city,
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
        self.dept1, self.city1 = create_geo('Antioquia', 'Medellín')
        self.dept2, self.city2 = create_geo('Cundinamarca', 'Bogotá')
        self.dept3, self.city3 = create_geo('Valle del Cauca', 'Cali')

    def test_create_address(self):
        data = {
            'recipient_name': 'Juan Perez',
            'phone': '3001234567',
            'address_line': 'Calle 10 # 20-30',
            'city': self.city1.pk,
            'department': self.dept1.pk,
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['user']['id'], self.user.pk)
        self.assertTrue(response.data['is_default'])

    def test_create_address_assigns_to_authenticated_user(self):
        data = {
            'recipient_name': 'Juan Perez',
            'address_line': 'Calle 10 # 20-30',
            'city': self.city1.pk,
            'department': self.dept1.pk,
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        addr = Address.objects.get(pk=response.data['id'])
        self.assertEqual(addr.user, self.user)

    def test_first_address_is_default(self):
        data = {
            'recipient_name': 'Primera',
            'address_line': 'Calle 10',
            'city': self.city2.pk,
            'department': self.dept2.pk,
        }
        response = self.client.post(self.url, data, format='json')
        self.assertTrue(response.data['is_default'])

    def test_second_address_is_not_default(self):
        self.client.post(self.url, {
            'recipient_name': 'Primera',
            'address_line': 'Calle 10',
            'city': self.city2.pk,
            'department': self.dept2.pk,
        }, format='json')
        data = {
            'recipient_name': 'Segunda',
            'address_line': 'Calle 20',
            'city': self.city3.pk,
            'department': self.dept3.pk,
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
            'city': self.city2.pk,
            'department': self.dept2.pk,
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
        self.dept2, self.city2 = create_geo('Atlántico', 'Barranquilla')
        self.url = reverse('direcciones-detail', args=[self.addr.pk])

    def test_update_own_address(self):
        self.client.force_authenticate(self.user)
        data = {
            'recipient_name': 'Nuevo Nombre',
            'address_line': 'Nueva Calle',
            'city': self.city2.pk,
            'department': self.dept2.pk,
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


class PasswordResetConfirmEmailTests(TestCase):

    def setUp(self):
        self.user = create_user()
        self.token_generator = PasswordResetTokenGenerator()
        self.token = self.token_generator.make_token(self.user)
        self.uid = self.user.pk

    def _get_confirm_url(self):
        from django.utils.http import urlsafe_base64_encode
        uidb64 = urlsafe_base64_encode(str(self.uid).encode())
        return reverse('users:password_reset_confirm', kwargs={'uidb64': uidb64, 'token': self.token})

    def test_send_email_on_successful_reset(self):
        mail.outbox = []
        url = self._get_confirm_url()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        confirm_url = response.url
        response = self.client.post(confirm_url, {
            'new_password1': 'NuevaPass123!',
            'new_password2': 'NuevaPass123!',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.subject, 'Tu contraseña de Carely fue actualizada')
        self.assertEqual(email.to, [self.user.email])

    def test_no_email_on_invalid_token(self):
        mail.outbox = []
        from django.utils.http import urlsafe_base64_encode
        uidb64 = urlsafe_base64_encode(str(self.user.pk).encode())
        url = reverse('users:password_reset_confirm', kwargs={'uidb64': uidb64, 'token': 'invalid-token'})
        self.client.get(url)
        response = self.client.post(url, {
            'new_password1': 'NuevaPass123!',
            'new_password2': 'NuevaPass123!',
        })
        self.assertEqual(len(mail.outbox), 0)


class PasswordChangeEmailTests(TestCase):

    def setUp(self):
        self.user = create_user()
        self.client.force_login(self.user)

    def test_send_email_on_successful_change(self):
        mail.outbox = []
        url = reverse('users:password_change')
        response = self.client.post(url, {
            'old_password': 'pass12345',
            'new_password1': 'NuevaPass123!',
            'new_password2': 'NuevaPass123!',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.subject, 'Tu contraseña de Carely fue actualizada')
        self.assertEqual(email.to, [self.user.email])

    def test_no_email_on_invalid_old_password(self):
        mail.outbox = []
        url = reverse('users:password_change')
        response = self.client.post(url, {
            'old_password': 'incorrecta',
            'new_password1': 'NuevaPass123!',
            'new_password2': 'NuevaPass123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)


class DepartmentCitiesApiTests(TestCase):

    def setUp(self):
        self.dept1, self.city1 = create_geo('Antioquia', 'Medellín')
        self.city1b = City.objects.create(api_id=10001, name='Envigado', department=self.dept1)
        self.dept2, self.city2 = create_geo('Cundinamarca', 'Bogotá')

    def test_returns_cities_of_department(self):
        url = reverse('users:department_cities_api', args=[self.dept1.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        ids = {c['id'] for c in data['cities']}
        self.assertEqual(ids, {self.city1.pk, self.city1b.pk})
        names = {c['name'] for c in data['cities']}
        self.assertEqual(names, {'Medellín', 'Envigado'})

    def test_includes_only_requested_department(self):
        url = reverse('users:department_cities_api', args=[self.dept2.pk])
        response = self.client.get(url)
        data = response.json()
        self.assertEqual([c['id'] for c in data['cities']], [self.city2.pk])

    def test_unknown_department_404(self):
        url = reverse('users:department_cities_api', args=[999999])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class AddressFormTests(TestCase):

    def setUp(self):
        self.user = create_user()
        self.dept1, self.city1 = create_geo('Antioquia', 'Medellín')
        self.dept2, self.city2 = create_geo('Cundinamarca', 'Bogotá')
        self.addr = Address.objects.create(
            user=self.user, recipient_name='Juan', address_line='Calle 1',
            department=self.dept1, city=self.city1,
        )

    def test_new_empty_form_has_no_cities(self):
        from apps.users.forms import AddressForm
        form = AddressForm()
        self.assertFalse(form.fields['city'].queryset.exists())
        self.assertEqual(list(form.fields['department'].queryset), [self.dept1, self.dept2])

    def test_edit_form_loads_cities_of_associated_department(self):
        from apps.users.forms import AddressForm
        form = AddressForm(instance=self.addr)
        self.assertEqual(
            list(form.fields['city'].queryset.order_by('pk')),
            [self.city1],
        )

    def test_post_filters_cities_by_submitted_department(self):
        from apps.users.forms import AddressForm
        form = AddressForm({
            'department': str(self.dept2.pk) if hasattr(self.dept2.pk, '__str__') else self.dept2.pk,
        })
        self.assertEqual(
            list(form.fields['city'].queryset.order_by('pk')),
            [self.city2],
        )

    def test_clean_rejects_city_from_other_department(self):
        from apps.users.forms import AddressForm
        form = AddressForm({
            'department': str(self.dept1.pk),
            'city': str(self.city2.pk),
            'recipient_name': 'Juan',
            'phone': '',
            'address_line': 'Calle',
            'address_line2': '',
            'postal_code': '',
            'instructions': '',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('city', form.errors)
