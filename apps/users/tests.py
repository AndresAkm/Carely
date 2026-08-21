from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from .models import User


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AuthenticationTests(TestCase):
    def setUp(self):
        self.password = 'ValidPassword123'
        self.user = User.objects.create_user(
            username='active@example.com', email='active@example.com', password=self.password
        )

    def test_user_can_login_with_email(self):
        response = self.client.post(reverse('users:login'), {
            'email': self.user.email, 'password': self.password,
        })
        self.assertRedirects(response, reverse('catalog:home'))

    def test_password_reset_only_sends_email_for_active_users(self):
        inactive = User.objects.create_user(
            username='inactive@example.com', email='inactive@example.com',
            password=self.password, is_active=False,
        )
        self.client.post(reverse('users:password_reset'), {'email': self.user.email})
        self.assertEqual(len(mail.outbox), 1)
        mail.outbox.clear()
        self.client.post(reverse('users:password_reset'), {'email': inactive.email})
        self.assertEqual(len(mail.outbox), 0)

    def test_jwt_token_is_issued(self):
        response = self.client.post('/api/v1/auth/token/', {
            'username': self.user.username, 'password': self.password,
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.json())
        self.assertIn('refresh', response.json())

    def test_admin_role_can_write_api(self):
        self.user.role = User.Role.ADMIN
        self.user.save(update_fields=['role'])
        client = APIClient()
        client.force_authenticate(user=self.user)
        response = client.post('/api/v1/catalogo/categorias/', {'name': 'Test', 'icon': 'bi-test'})
        self.assertEqual(response.status_code, 201)
