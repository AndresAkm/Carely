from datetime import timedelta
import re
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Address, City, Department, TwoFactorCode, User
from .services import GmailServiceError, build_reactivation_token


def create_user(**kwargs):
    defaults = {
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'pass12345',
    }
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)


def issue_two_factor_code(user, purpose, code='123456', ttl_seconds=None):
    """Deja un código vigente como si el usuario lo hubiera recibido por correo."""
    expires_in = settings.TWO_FACTOR_CODE_TTL if ttl_seconds is None else ttl_seconds
    return TwoFactorCode.objects.create(
        user=user,
        purpose=purpose,
        code_hash=make_password(code),
        expires_at=timezone.now() + timedelta(seconds=expires_in),
    )


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


class AccountDeactivateTests(TestCase):

    def setUp(self):
        self.user = create_user()
        self.user.two_factor_enabled = True
        self.user.save()
        self.url = reverse('users:account_deactivate')
        self.code = '123456'

    def deactivate(self, **overrides):
        issue_two_factor_code(self.user, TwoFactorCode.Purpose.DEACTIVATE, self.code)
        data = {'password': 'pass12345', 'confirm': 'on', 'code': self.code}
        data.update(overrides)
        return self.client.post(self.url, data)

    def test_requires_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('users:login'), response.url)

    def test_two_factor_is_required_before_deactivating(self):
        self.user.two_factor_enabled = False
        self.user.save()
        self.client.force_login(self.user)
        response = self.client.post(self.url, {'password': 'pass12345', 'confirm': 'on'})
        self.assertRedirects(response, reverse('users:two_factor_setup'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_get_renders_confirmation_page_and_sends_the_code(self):
        mail.outbox = []
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/deactivate_account.html')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Tu código de verificación de Carely')
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        self.assertTrue(
            TwoFactorCode.objects.filter(
                user=self.user, purpose=TwoFactorCode.Purpose.DEACTIVATE, used_at__isnull=True,
            ).exists()
        )

    def test_get_renders_the_code_as_digit_boxes(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        # El input real sigue siendo el que envía el formulario.
        self.assertContains(response, 'name="code"')
        self.assertContains(response, 'data-code-input')
        self.assertContains(response, 'data-code-box', count=settings.TWO_FACTOR_CODE_LENGTH)
        self.assertContains(response, 'users/js/code_input.js')

    def test_get_does_not_resend_a_pending_code(self):
        issue_two_factor_code(self.user, TwoFactorCode.Purpose.DEACTIVATE, self.code)
        mail.outbox = []
        self.client.force_login(self.user)
        self.client.get(self.url)
        self.assertEqual(len(mail.outbox), 0)

    def test_deactivates_account_and_logs_out(self):
        self.client.force_login(self.user)
        response = self.deactivate()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('core:home'))
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_records_who_and_when_deactivated(self):
        self.client.force_login(self.user)
        self.deactivate()
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.deactivated_at)
        self.assertIsNone(self.user.deactivated_by)
        self.assertFalse(self.user.was_deactivated_by_admin)

    def test_email_to_user_carries_reactivation_link(self):
        mail.outbox = []
        self.client.force_login(self.user)
        self.deactivate()
        self.assertEqual(len(mail.outbox), 2)
        email = mail.outbox[0]
        self.assertEqual(email.subject, 'Tu cuenta Carely fue deshabilitada')
        self.assertEqual(email.to, [self.user.email])
        self.assertIn(reverse('users:account_reactivate', args=[build_reactivation_token(self.user)]), email.body)

    def test_notice_goes_to_support_without_reactivation_link(self):
        mail.outbox = []
        self.client.force_login(self.user)
        self.deactivate()
        notice = mail.outbox[1]
        self.assertEqual(notice.subject, f'Cuenta deshabilitada: {self.user.email}')
        self.assertEqual(notice.to, [settings.CARELY_EMAIL])
        self.assertIn('El titular de la cuenta', notice.body)
        self.assertNotIn('/accounts/reactivar-cuenta/', notice.body)

    def test_account_stays_deactivated_when_email_fails(self):
        issue_two_factor_code(self.user, TwoFactorCode.Purpose.DEACTIVATE, self.code)
        with patch('apps.users.services.GmailService.send_message', side_effect=GmailServiceError('sin red')):
            mail.outbox = []
            self.client.force_login(self.user)
            response = self.client.post(self.url, {
                'password': 'pass12345', 'confirm': 'on', 'code': self.code,
            })
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertEqual(len(mail.outbox), 0)

    def test_inactive_user_cannot_login_afterwards(self):
        from django.contrib.auth import authenticate
        self.client.force_login(self.user)
        self.deactivate()
        self.client.logout()
        response = self.client.post(reverse('users:login'), {
            'email': self.user.email,
            'password': 'pass12345',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('users:account_paused'))
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertIsNone(authenticate(username=self.user.email, password='pass12345'))

    def test_wrong_password_keeps_account_active(self):
        self.client.force_login(self.user)
        response = self.deactivate(password='incorrecta')
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertIn('password', response.context['form'].errors)

    def test_missing_confirmation_keeps_account_active(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, {
            'password': 'pass12345', 'code': self.code, 'confirm': '',
        })
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertIn('confirm', response.context['form'].errors)

    def test_missing_confirmation_does_not_consume_the_code(self):
        self.client.force_login(self.user)
        issue_two_factor_code(self.user, TwoFactorCode.Purpose.DEACTIVATE, self.code)
        self.client.post(self.url, {'password': 'pass12345', 'code': self.code})
        self.assertFalse(
            TwoFactorCode.objects.filter(
                user=self.user, purpose=TwoFactorCode.Purpose.DEACTIVATE, used_at__isnull=True,
            ).exists()
        )

    def test_wrong_code_keeps_account_active(self):
        self.client.force_login(self.user)
        response = self.deactivate(code='000000')
        self.assertEqual(response.status_code, 200)
        self.assertIn('code', response.context['form'].errors)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_missing_code_keeps_account_active(self):
        self.client.force_login(self.user)
        response = self.deactivate(code='')
        self.assertEqual(response.status_code, 200)
        self.assertIn('code', response.context['form'].errors)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_code_cannot_be_used_twice(self):
        self.client.force_login(self.user)
        issue_two_factor_code(self.user, TwoFactorCode.Purpose.DEACTIVATE, self.code)
        payload = {'password': 'pass12345', 'confirm': 'on', 'code': self.code}
        self.assertEqual(self.client.post(self.url, payload).status_code, 302)
        self.user.refresh_from_db()
        self.user.is_active = True
        self.user.save()
        self.client.force_login(self.user)
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn('code', response.context['form'].errors)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_expired_code_keeps_account_active(self):
        self.client.force_login(self.user)
        issue_two_factor_code(self.user, TwoFactorCode.Purpose.DEACTIVATE, self.code, ttl_seconds=-10)
        response = self.client.post(self.url, {
            'password': 'pass12345', 'confirm': 'on', 'code': self.code,
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('code', response.context['form'].errors)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_get_replaces_an_expired_code(self):
        self.client.force_login(self.user)
        issue_two_factor_code(self.user, TwoFactorCode.Purpose.DEACTIVATE, self.code, ttl_seconds=-10)
        mail.outbox = []
        self.client.get(self.url)
        self.assertEqual(len(mail.outbox), 1)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_code_is_locked_after_too_many_attempts(self):
        self.client.force_login(self.user)
        locked_code = issue_two_factor_code(self.user, TwoFactorCode.Purpose.DEACTIVATE, self.code)
        locked_code.failed_attempts = settings.TWO_FACTOR_MAX_ATTEMPTS
        locked_code.save(update_fields=['failed_attempts'])
        response = self.client.post(self.url, {
            'password': 'pass12345', 'confirm': 'on', 'code': self.code,
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('code', response.context['form'].errors)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_resend_replaces_the_previous_code(self):
        issue_two_factor_code(self.user, TwoFactorCode.Purpose.DEACTIVATE, self.code)
        mail.outbox = []
        self.client.force_login(self.user)
        response = self.client.post(self.url, {'resend': '1'})
        self.assertRedirects(response, self.url)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            TwoFactorCode.objects.filter(
                user=self.user, purpose=TwoFactorCode.Purpose.DEACTIVATE, used_at__isnull=True,
            ).count(),
            1,
        )

    def test_admin_is_redirected_to_dashboard(self):
        admin = create_user(
            username='admin', email='admin@example.com',
            role=User.Role.ADMIN, is_staff=True,
        )
        self.client.force_login(admin)
        response = self.client.post(self.url, {
            'password': 'pass12345', 'confirm': 'on', 'code': self.code,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('core:dashboard'))
        admin.refresh_from_db()
        self.assertTrue(admin.is_active)


class TwoFactorSetupTests(TestCase):

    def setUp(self):
        self.user = create_user()
        self.url = reverse('users:two_factor_setup')
        self.code = '123456'

    def test_requires_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('users:login'), response.url)

    def test_get_sends_a_code_once(self):
        mail.outbox = []
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/two_factor_setup.html')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Tu código de verificación de Carely')
        self.assertEqual(mail.outbox[0].to, [self.user.email])

    def test_get_does_not_resend_a_pending_code(self):
        issue_two_factor_code(self.user, TwoFactorCode.Purpose.ENABLE, self.code)
        mail.outbox = []
        self.client.force_login(self.user)
        self.client.get(self.url)
        self.assertEqual(len(mail.outbox), 0)

    def test_activating_renders_the_code_as_digit_boxes(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, 'name="code"')
        self.assertContains(response, 'data-code-box', count=settings.TWO_FACTOR_CODE_LENGTH)
        self.assertContains(response, 'users/css/code_input.css')

    def test_disabling_also_renders_the_digit_boxes(self):
        self.user.two_factor_enabled = True
        self.user.save()
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, 'name="code"')
        self.assertContains(response, 'data-code-box', count=settings.TWO_FACTOR_CODE_LENGTH)

    def test_the_back_link_keeps_the_card_padding(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        # Sin el envoltorio .profile-form el botón queda pegado al borde.
        self.assertRegex(
            response.content.decode(),
            r'<div class="profile-form profile-form--single">\s*'
            r'<div class="profile-form-actions">\s*'
            r'<a href="' + re.escape(reverse('users:profile')) + r'"',
        )

    def test_get_replaces_an_expired_code(self):
        issue_two_factor_code(self.user, TwoFactorCode.Purpose.ENABLE, self.code, ttl_seconds=-10)
        mail.outbox = []
        self.client.force_login(self.user)
        self.client.get(self.url)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(TwoFactorCode.objects.filter(user=self.user).count(), 1)
        self.assertTrue(
            TwoFactorCode.objects.get(user=self.user).is_usable
        )

    def test_disabling_sends_the_code_too(self):
        self.user.two_factor_enabled = True
        self.user.save()
        mail.outbox = []
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(
            TwoFactorCode.objects.filter(
                user=self.user, purpose=TwoFactorCode.Purpose.ENABLE, used_at__isnull=True,
            ).exists()
        )

    def test_correct_code_activates_two_factor(self):
        self.client.force_login(self.user)
        issue_two_factor_code(self.user, TwoFactorCode.Purpose.ENABLE, self.code)
        response = self.client.post(self.url, {'code': self.code})
        self.assertRedirects(response, self.url)
        self.user.refresh_from_db()
        self.assertTrue(self.user.two_factor_enabled)
        self.assertIsNotNone(self.user.two_factor_enabled_at)

    def test_wrong_code_keeps_two_factor_disabled(self):
        self.client.force_login(self.user)
        issue_two_factor_code(self.user, TwoFactorCode.Purpose.ENABLE, self.code)
        response = self.client.post(self.url, {'code': '000000'})
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(self.user.two_factor_enabled)

    def test_expired_code_keeps_two_factor_disabled(self):
        self.client.force_login(self.user)
        issue_two_factor_code(self.user, TwoFactorCode.Purpose.ENABLE, self.code, ttl_seconds=-10)
        response = self.client.post(self.url, {'code': self.code})
        self.assertEqual(response.status_code, 200)
        self.assertIn('code', response.context['form'].errors)
        self.user.refresh_from_db()
        self.assertFalse(self.user.two_factor_enabled)

    def test_activation_code_is_locked_after_too_many_attempts(self):
        self.client.force_login(self.user)
        issue_two_factor_code(self.user, TwoFactorCode.Purpose.ENABLE, self.code)
        for _ in range(settings.TWO_FACTOR_MAX_ATTEMPTS):
            response = self.client.post(self.url, {'code': '000000'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('Demasiados intentos', str(response.context['form'].errors['code']))
        self.user.refresh_from_db()
        self.assertFalse(self.user.two_factor_enabled)

    def test_asking_for_a_code_without_one_pending(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, {'code': self.code})
        self.assertEqual(response.status_code, 200)
        self.assertIn('Pide un código', str(response.context['form'].errors['code']))

    def test_resend_replaces_the_previous_code(self):
        issue_two_factor_code(self.user, TwoFactorCode.Purpose.ENABLE, self.code)
        mail.outbox = []
        self.client.force_login(self.user)
        response = self.client.post(self.url, {'resend': '1'})
        self.assertRedirects(response, self.url)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            TwoFactorCode.objects.filter(
                user=self.user, purpose=TwoFactorCode.Purpose.ENABLE, used_at__isnull=True,
            ).count(),
            1,
        )

    def test_disable_asks_for_password_and_code(self):
        self.user.two_factor_enabled = True
        self.user.save()
        self.client.force_login(self.user)
        response = self.client.post(self.url, {'password': 'incorrecta', 'code': self.code})
        self.assertEqual(response.status_code, 200)
        self.assertIn('password', response.context['form'].errors)
        self.user.refresh_from_db()
        self.assertTrue(self.user.two_factor_enabled)

    def test_disable_turns_two_factor_off_and_drops_pending_codes(self):
        self.user.two_factor_enabled = True
        self.user.save()
        issue_two_factor_code(self.user, TwoFactorCode.Purpose.ENABLE, self.code)
        self.client.force_login(self.user)
        response = self.client.post(self.url, {'password': 'pass12345', 'code': self.code})
        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertFalse(self.user.two_factor_enabled)
        self.assertIsNone(self.user.two_factor_enabled_at)
        self.assertFalse(
            TwoFactorCode.objects.filter(user=self.user, used_at__isnull=True).exists()
        )

    def test_disabling_needs_a_fresh_code(self):
        self.user.two_factor_enabled = True
        self.user.save()
        self.client.force_login(self.user)
        self.client.post(self.url, {'password': 'pass12345', 'code': self.code})
        response = self.client.post(self.url, {'password': 'pass12345', 'code': self.code})
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.two_factor_enabled)

    def test_admin_is_redirected_to_dashboard(self):
        admin = create_user(
            username='admin', email='admin@example.com',
            role=User.Role.ADMIN, is_staff=True,
        )
        self.client.force_login(admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('core:dashboard'))
        admin.refresh_from_db()
        self.assertFalse(admin.two_factor_enabled)


class PausedAccountTests(TestCase):

    def setUp(self):
        # El login autentica por username, y el registro lo guarda igual al email.
        self.user = create_user(username='test@example.com', email='test@example.com')
        self.user.is_active = False
        self.user.deactivated_at = timezone.now()
        self.user.save()
        self.login_url = reverse('users:login')
        self.paused_url = reverse('users:account_paused')
        self.code = '123456'

    def login_with_paused_account(self, password='pass12345'):
        return self.client.post(self.login_url, {
            'email': self.user.email,
            'password': password,
        })

    def deactivate_by_admin(self):
        admin = create_user(
            username='admin', email='admin@example.com',
            role=User.Role.ADMIN, is_staff=True,
        )
        self.user.deactivated_by = admin
        self.user.save()
        return admin

    def test_correct_password_lands_on_paused_screen(self):
        response = self.login_with_paused_account()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.paused_url)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertTemplateUsed(self.client.get(self.paused_url), 'users/paused_account.html')

    def test_screen_renders_the_code_as_digit_boxes(self):
        self.login_with_paused_account()
        response = self.client.get(self.paused_url)
        self.assertContains(response, 'name="code"')
        self.assertContains(response, 'data-code-box', count=settings.TWO_FACTOR_CODE_LENGTH)
        self.assertContains(response, 'users/css/code_input.css')

    def test_no_digit_boxes_when_an_admin_deactivated_it(self):
        self.deactivate_by_admin()
        self.login_with_paused_account()
        response = self.client.get(self.paused_url)
        self.assertNotContains(response, 'data-code-box')

    def test_wrong_password_does_not_reveal_the_status(self):
        response = self.login_with_paused_account(password='incorrecta')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/login.html')
        self.assertNotContains(response, 'está pausada')

    def test_active_account_does_not_see_paused_screen(self):
        self.user.is_active = True
        self.user.save()
        response = self.login_with_paused_account()
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(response.url, self.paused_url)

    def test_paused_screen_needs_the_login_session(self):
        response = self.client.get(self.paused_url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.login_url)

    def test_screen_sends_a_reactivation_code(self):
        mail.outbox = []
        self.login_with_paused_account()
        response = self.client.get(self.paused_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Tu código de verificación de Carely')
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        self.assertTrue(
            TwoFactorCode.objects.filter(
                user=self.user, purpose=TwoFactorCode.Purpose.REACTIVATE, used_at__isnull=True,
            ).exists()
        )

    def test_screen_resends_the_code_on_demand(self):
        issue_two_factor_code(self.user, TwoFactorCode.Purpose.REACTIVATE, self.code)
        mail.outbox = []
        self.login_with_paused_account()
        response = self.client.post(self.paused_url, {'resend': '1'})
        self.assertRedirects(response, self.paused_url)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Tu código de verificación de Carely')

    def test_correct_code_reactivates_the_account(self):
        self.login_with_paused_account()
        issue_two_factor_code(self.user, TwoFactorCode.Purpose.REACTIVATE, self.code)
        response = self.client.post(self.paused_url, {'code': self.code})
        self.assertRedirects(response, self.login_url, fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertIsNone(self.user.deactivated_at)
        self.assertNotIn('paused_user_id', self.client.session)

    def test_reactivated_user_can_login_again(self):
        self.login_with_paused_account()
        issue_two_factor_code(self.user, TwoFactorCode.Purpose.REACTIVATE, self.code)
        self.client.post(self.paused_url, {'code': self.code})
        response = self.client.post(self.login_url, {
            'email': self.user.email,
            'password': 'pass12345',
        })
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(response.url, self.paused_url)
        self.assertIn('_auth_user_id', self.client.session)

    def test_wrong_code_keeps_the_account_paused(self):
        self.login_with_paused_account()
        issue_two_factor_code(self.user, TwoFactorCode.Purpose.REACTIVATE, self.code)
        response = self.client.post(self.paused_url, {'code': '000000'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('code', response.context['form'].errors)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_code_is_refused_without_the_login_session(self):
        issue_two_factor_code(self.user, TwoFactorCode.Purpose.REACTIVATE, self.code)
        response = self.client.post(self.paused_url, {'code': self.code})
        self.assertRedirects(response, self.login_url, fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_expired_code_keeps_the_account_paused(self):
        self.login_with_paused_account()
        issue_two_factor_code(self.user, TwoFactorCode.Purpose.REACTIVATE, self.code, ttl_seconds=-10)
        response = self.client.post(self.paused_url, {'code': self.code})
        self.assertEqual(response.status_code, 200)
        self.assertIn('code', response.context['form'].errors)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_code_cannot_be_used_twice(self):
        self.login_with_paused_account()
        issue_two_factor_code(self.user, TwoFactorCode.Purpose.REACTIVATE, self.code)
        self.assertEqual(self.client.post(self.paused_url, {'code': self.code}).status_code, 302)
        self.user.is_active = False
        self.user.deactivated_at = timezone.now()
        self.user.save()
        self.login_with_paused_account()
        response = self.client.post(self.paused_url, {'code': self.code})
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_screen_replaces_an_expired_code(self):
        self.login_with_paused_account()
        issue_two_factor_code(self.user, TwoFactorCode.Purpose.REACTIVATE, self.code, ttl_seconds=-10)
        mail.outbox = []
        self.client.get(self.paused_url)
        self.assertEqual(len(mail.outbox), 1)

    def test_screen_does_not_resend_a_pending_code(self):
        self.login_with_paused_account()
        issue_two_factor_code(self.user, TwoFactorCode.Purpose.REACTIVATE, self.code)
        mail.outbox = []
        self.client.get(self.paused_url)
        self.assertEqual(len(mail.outbox), 0)

    def test_screen_offers_support_when_an_admin_deactivated_it(self):
        self.deactivate_by_admin()
        self.login_with_paused_account()
        response = self.client.get(self.paused_url)
        self.assertContains(response, settings.CARELY_EMAIL)
        self.assertNotContains(response, 'Reactivar mi cuenta')

    def test_admin_deactivated_account_ignores_the_code(self):
        self.deactivate_by_admin()
        session = self.client.session
        session['paused_user_id'] = self.user.pk
        session.save()
        issue_two_factor_code(self.user, TwoFactorCode.Purpose.REACTIVATE, self.code)
        response = self.client.post(self.paused_url, {'code': self.code})
        self.assertRedirects(response, self.login_url, fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_no_code_is_sent_when_an_admin_deactivated_it(self):
        self.deactivate_by_admin()
        mail.outbox = []
        session = self.client.session
        session['paused_user_id'] = self.user.pk
        session.save()
        self.client.get(self.paused_url)
        self.assertEqual(len(mail.outbox), 0)

    def test_resend_is_refused_when_an_admin_deactivated_it(self):
        self.deactivate_by_admin()
        mail.outbox = []
        session = self.client.session
        session['paused_user_id'] = self.user.pk
        session.save()
        response = self.client.post(self.paused_url, {'resend': '1'})
        self.assertRedirects(response, self.login_url, fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 0)


class ReactivateAccountTests(TestCase):

    def setUp(self):
        self.user = create_user(username='test@example.com', email='test@example.com')
        self.user.is_active = False
        self.user.deactivated_at = timezone.now()
        self.user.save()

    def reactivate_url(self, user=None):
        user = user or self.user
        return reverse('users:account_reactivate', args=[build_reactivation_token(user)])

    def test_get_shows_confirmation_page(self):
        response = self.client.get(self.reactivate_url())
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/reactivate_account.html')
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_post_reactivates_and_clears_the_audit_trail(self):
        response = self.client.post(self.reactivate_url())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('users:login'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertIsNone(self.user.deactivated_at)
        self.assertIsNone(self.user.deactivated_by)

    def test_reactivated_user_can_login_again(self):
        self.client.post(self.reactivate_url())
        response = self.client.post(reverse('users:login'), {
            'email': self.user.email,
            'password': 'pass12345',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('_auth_user_id', self.client.session)

    def test_token_of_an_admin_deactivated_account_is_refused(self):
        admin = create_user(
            username='admin', email='admin@example.com',
            role=User.Role.ADMIN, is_staff=True,
        )
        self.user.deactivated_by = admin
        self.user.save()
        response = self.client.post(self.reactivate_url())
        self.assertContains(response, 'El enlace no es válido')
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_token_stops_working_once_the_account_is_active(self):
        url = self.reactivate_url()
        self.client.post(url)
        response = self.client.post(url)
        self.assertContains(response, 'El enlace no es válido')
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_forged_token_explains_that_the_link_is_invalid(self):
        url = reverse('users:account_reactivate', args=['token-falso'])
        self.assertContains(self.client.get(url), 'El enlace no es válido')
        self.assertContains(self.client.post(url), 'El enlace no es válido')

    @override_settings(ACCOUNT_REACTIVATION_TIMEOUT=-1)
    def test_expired_token_explains_that_the_link_is_invalid(self):
        response = self.client.post(self.reactivate_url())
        self.assertContains(response, 'El enlace no es válido')
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)


class DashboardDeactivationAuditTests(TestCase):

    def setUp(self):
        self.admin = create_user(
            username='admin', email='admin@example.com',
            role=User.Role.ADMIN, is_staff=True,
        )
        self.client_user = create_user()
        self.toggle_url = reverse('dashboard:user_toggle_active', args=[self.client_user.pk])
        self.update_url = reverse('dashboard:user_update', args=[self.client_user.pk])

    def test_toggle_records_the_admin_and_notifies(self):
        mail.outbox = []
        self.client.force_login(self.admin)
        response = self.client.post(self.toggle_url)
        self.assertEqual(response.status_code, 302)
        self.client_user.refresh_from_db()
        self.assertFalse(self.client_user.is_active)
        self.assertEqual(self.client_user.deactivated_by, self.admin)
        self.assertIsNotNone(self.client_user.deactivated_at)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[0].to, [self.client_user.email])
        self.assertEqual(mail.outbox[1].to, [settings.CARELY_EMAIL])

    def test_toggle_email_to_user_has_no_reactivation_link(self):
        mail.outbox = []
        self.client.force_login(self.admin)
        self.client.post(self.toggle_url)
        self.assertNotIn('/accounts/reactivar-cuenta/', mail.outbox[0].body)
        self.assertIn(settings.CARELY_EMAIL, mail.outbox[0].body)

    def test_edit_form_records_the_admin_and_notifies(self):
        mail.outbox = []
        self.client.force_login(self.admin)
        response = self.client.post(self.update_url, {
            'first_name': 'Ana',
            'last_name': 'Restrepo',
            'email': self.client_user.email,
            'phone': '',
            'role': User.Role.CLIENT,
        })
        self.assertEqual(response.status_code, 302)
        self.client_user.refresh_from_db()
        self.assertFalse(self.client_user.is_active)
        self.assertEqual(self.client_user.deactivated_by, self.admin)
        self.assertEqual(len(mail.outbox), 2)

    def test_edit_form_keeps_the_other_edited_fields(self):
        self.client.force_login(self.admin)
        self.client.post(self.update_url, {
            'first_name': 'Ana',
            'last_name': 'Restrepo',
            'email': self.client_user.email,
            'phone': '3001234567',
            'role': User.Role.CLIENT,
        })
        self.client_user.refresh_from_db()
        self.assertFalse(self.client_user.is_active)
        self.assertEqual(self.client_user.first_name, 'Ana')
        self.assertEqual(self.client_user.phone, '3001234567')

    def test_toggle_back_clears_the_audit_trail(self):
        self.client.force_login(self.admin)
        self.client.post(self.toggle_url)
        self.client.post(self.toggle_url)
        self.client_user.refresh_from_db()
        self.assertTrue(self.client_user.is_active)
        self.assertIsNone(self.client_user.deactivated_at)
        self.assertIsNone(self.client_user.deactivated_by)


def register_payload(**overrides):
    payload = {
        'first_name': 'Ana',
        'last_name': 'Restrepo',
        'email': 'ana@example.com',
        'password1': 'Pass1234',
        'password2': 'Pass1234',
        'accept_terms': 'on',
    }
    payload.update(overrides)
    return payload


class RegisterTermsAcceptanceTests(TestCase):

    def test_checkbox_is_rendered_on_register_page(self):
        response = self.client.get(reverse('users:register'))
        self.assertContains(response, 'name="accept_terms"')
        self.assertContains(response, 'Términos y Condiciones')
        self.assertContains(response, 'Política de Privacidad')
        self.assertContains(response, reverse('core:privacy'))

    def test_checkbox_links_point_to_legal_sections(self):
        response = self.client.get(reverse('users:register'))
        self.assertContains(response, '/privacidad/#terminos')
        self.assertContains(response, '/privacidad/#privacidad')

    def test_registration_fails_without_acceptance(self):
        payload = register_payload()
        del payload['accept_terms']
        response = self.client.post(reverse('users:register'), payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors.get('accept_terms'))
        self.assertFalse(User.objects.filter(email='ana@example.com').exists())

    def test_registration_records_acceptance(self):
        response = self.client.post(reverse('users:register'), register_payload())
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email='ana@example.com')
        self.assertIsNotNone(user.accepted_terms_at)
        self.assertEqual(user.terms_version, settings.TERMS_VERSION)
        self.assertTrue(user.has_accepted_current_terms)

    def test_acceptance_timestamp_is_set_once(self):
        self.client.post(reverse('users:register'), register_payload())
        user = User.objects.get(email='ana@example.com')
        first_seen = user.accepted_terms_at
        self.client.logout()
        self.client.post(reverse('users:register'), register_payload(email='otro@example.com'))
        user.refresh_from_db()
        self.assertEqual(user.accepted_terms_at, first_seen)

    def test_existing_users_have_no_recorded_acceptance(self):
        user = create_user()
        self.assertIsNone(user.accepted_terms_at)
        self.assertEqual(user.terms_version, '')
        self.assertFalse(user.has_accepted_current_terms)

    def test_stale_terms_version_is_detected(self):
        user = create_user()
        user.accepted_terms_at = timezone.now()
        user.terms_version = '1999-01-01'
        user.save()
        self.assertFalse(user.has_accepted_current_terms)


class LoginTermsNoticeTests(TestCase):

    def test_login_page_shows_notice_without_checkbox(self):
        response = self.client.get(reverse('users:login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'auth-browsewrap')
        self.assertContains(response, 'Términos y Condiciones')
        self.assertContains(response, 'Política de Privacidad')

    def test_login_page_has_no_required_checkbox(self):
        response = self.client.get(reverse('users:login'))
        self.assertNotContains(response, 'name="accept_terms"')

    def test_login_works_without_ticking_anything(self):
        # El registro guarda username = email, que es lo que usa LoginView para autenticar.
        create_user(username='ana@example.com', email='ana@example.com', password='Pass1234')
        response = self.client.post(reverse('users:login'), {
            'email': 'ana@example.com',
            'password': 'Pass1234',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('_auth_user_id', self.client.session)


class LegalPageTests(TestCase):

    def test_privacy_page_is_public(self):
        response = self.client.get(reverse('core:privacy'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/legal.html')
        self.assertContains(response, 'Términos y Condiciones')
        self.assertContains(response, 'Ley 1581 de 2012')

    def test_privacy_page_url_at_root(self):
        response = self.client.get('/privacidad/')
        self.assertEqual(response.status_code, 200)

    def test_contact_details_come_from_context(self):
        response = self.client.get(reverse('core:privacy'))
        self.assertEqual(response.context['carely_email'], settings.CARELY_EMAIL)
        self.assertContains(response, settings.CARELY_EMAIL)

    def test_terms_page_shows_effective_date(self):
        response = self.client.get(reverse('core:privacy'))
        self.assertContains(response, settings.TERMS_EFFECTIVE_DATE)

    def test_terms_page_mentions_acceptance_checkbox(self):
        response = self.client.get(reverse('core:privacy'))
        self.assertContains(response, 'casilla de aceptación')

    def test_groups_have_sections(self):
        response = self.client.get(reverse('core:privacy'))
        groups = response.context['legal_groups']
        self.assertEqual([group['id'] for group in groups], ['terminos', 'privacidad'])
        for group in groups:
            self.assertTrue(group['sections'])
            for section in group['sections']:
                self.assertTrue(section['paragraphs'])


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
