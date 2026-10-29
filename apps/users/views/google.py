import secrets
import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from ..forms import GoogleCompleteRegistrationForm
from ..google_oauth import (
    GoogleOAuthError,
    build_authorization_url,
    exchange_code,
    fetch_userinfo,
    is_configured,
)
from ..models import User
from ..services import GmailService, GmailServiceError
from .web import PAUSED_USER_SESSION_KEY, get_redirect_url

GOOGLE_STATE_SESSION_KEY = 'google_oauth_state'
GOOGLE_STATE_CREATED_KEY = 'google_oauth_state_created'
GOOGLE_PENDING_SESSION_KEY = 'google_oauth_pending'
GOOGLE_STATE_TTL = 600
GOOGLE_PENDING_TTL = 900
GOOGLE_LOGIN_ERROR = 'No pudimos iniciar sesión con Google. Inténtalo de nuevo.'


def get_google_redirect_uri(request):
    if settings.GOOGLE_OAUTH_REDIRECT_URI:
        return settings.GOOGLE_OAUTH_REDIRECT_URI
    return request.build_absolute_uri(reverse('users:google_callback'))


def clear_google_state(request):
    request.session.pop(GOOGLE_STATE_SESSION_KEY, None)
    request.session.pop(GOOGLE_STATE_CREATED_KEY, None)


def clear_google_pending(request):
    request.session.pop(GOOGLE_PENDING_SESSION_KEY, None)


def login_google_user(request, user):
    clear_google_pending(request)
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    request.session.pop(PAUSED_USER_SESSION_KEY, None)
    name = user.first_name or user.email
    messages.success(request, f'¡Bienvenida de nuevo, {name}!')
    return redirect(get_redirect_url(user))


def handle_inactive_google_user(request, user):
    if user.was_deactivated_by_admin:
        messages.error(
            request,
            f'Tu cuenta está deshabilitada. Escríbenos a {settings.CARELY_EMAIL}.',
        )
        return redirect('users:login')
    request.session[PAUSED_USER_SESSION_KEY] = user.pk
    messages.info(request, 'Tu cuenta está deshabilitada. Puedes reactivarla desde aquí.')
    return redirect('users:account_paused')


def link_google_account(request, user, google_sub):
    if user.google_sub and user.google_sub != google_sub:
        messages.error(request, 'Esta cuenta ya está vinculada a otra cuenta de Google.')
        return redirect('users:login')
    if not user.is_active:
        return handle_inactive_google_user(request, user)
    if not user.google_sub:
        user.google_sub = google_sub
        user.save(update_fields=['google_sub', 'updated_at'])
        try:
            GmailService.send_google_link_notice(user)
        except GmailServiceError:
            pass
        messages.info(request, 'Vinculamos tu cuenta Carely con Google.')
    return login_google_user(request, user)


class GoogleLoginView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect(get_redirect_url(request.user))
        if not is_configured():
            messages.error(request, 'El inicio de sesión con Google no está disponible.')
            return redirect('users:login')

        clear_google_pending(request)
        state = secrets.token_urlsafe(32)
        request.session[GOOGLE_STATE_SESSION_KEY] = state
        request.session[GOOGLE_STATE_CREATED_KEY] = int(time.time())
        try:
            url = build_authorization_url(get_google_redirect_uri(request), state)
        except GoogleOAuthError:
            clear_google_state(request)
            messages.error(request, GOOGLE_LOGIN_ERROR)
            return redirect('users:login')
        return redirect(url)


class GoogleCallbackView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect(get_redirect_url(request.user))
        if not is_configured():
            messages.error(request, 'El inicio de sesión con Google no está disponible.')
            return redirect('users:login')

        expected_state = request.session.pop(GOOGLE_STATE_SESSION_KEY, '')
        created_at = request.session.pop(GOOGLE_STATE_CREATED_KEY, 0)
        error = request.GET.get('error', '')
        state = request.GET.get('state', '')
        code = request.GET.get('code', '')

        if error:
            messages.info(request, 'Cancelaste el inicio de sesión con Google.')
            return redirect('users:login')
        if not expected_state or not state or not secrets.compare_digest(expected_state, state):
            messages.error(request, GOOGLE_LOGIN_ERROR)
            return redirect('users:login')
        try:
            expired = int(created_at) + GOOGLE_STATE_TTL < int(time.time())
        except (TypeError, ValueError):
            expired = True
        if expired:
            messages.error(request, 'El enlace de autenticación expiró. Inténtalo de nuevo.')
            return redirect('users:login')
        if not code:
            messages.error(request, GOOGLE_LOGIN_ERROR)
            return redirect('users:login')

        try:
            access_token = exchange_code(code, get_google_redirect_uri(request))
            profile = fetch_userinfo(access_token)
        except GoogleOAuthError as error:
            messages.error(request, str(error))
            return redirect('users:login')

        google_sub = profile['sub']
        email = profile['email'].strip().lower()
        user = User.objects.filter(google_sub=google_sub).first()
        if user is not None:
            if not user.is_active:
                return handle_inactive_google_user(request, user)
            return login_google_user(request, user)

        existing = User.objects.filter(email__iexact=email).first()
        if existing is not None:
            return link_google_account(request, existing, google_sub)

        first_name = (profile.get('given_name') or profile.get('name') or '').strip()[:150]
        last_name = (profile.get('family_name') or '').strip()[:150]
        if not first_name:
            first_name = email.split('@')[0][:150]
        request.session[GOOGLE_PENDING_SESSION_KEY] = {
            'sub': google_sub,
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
            'created_at': int(time.time()),
        }
        return redirect('users:google_complete')


class GoogleCompleteRegistrationView(View):
    template_name = 'users/google_complete.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect(get_redirect_url(request.user))
        pending = self.get_pending(request)
        if pending is None:
            messages.error(request, 'El registro con Google expiró. Inténtalo de nuevo.')
            return redirect('users:login')
        return render(request, self.template_name, {
            'form': GoogleCompleteRegistrationForm(),
            'pending': pending,
        })

    def post(self, request):
        if request.user.is_authenticated:
            return redirect(get_redirect_url(request.user))
        pending = self.get_pending(request)
        if pending is None:
            messages.error(request, 'El registro con Google expiró. Inténtalo de nuevo.')
            return redirect('users:login')
        form = GoogleCompleteRegistrationForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {
                'form': form,
                'pending': pending,
            })
        return self.create_user(request, pending)

    def get_pending(self, request):
        pending = request.session.get(GOOGLE_PENDING_SESSION_KEY)
        if not isinstance(pending, dict):
            return None
        try:
            expired = int(pending.get('created_at', 0)) + GOOGLE_PENDING_TTL < int(time.time())
        except (TypeError, ValueError):
            expired = True
        if expired or not pending.get('sub') or not pending.get('email'):
            clear_google_pending(request)
            return None
        return pending

    def create_user(self, request, pending):
        google_sub = pending['sub']
        email = pending['email']

        user = User.objects.filter(google_sub=google_sub).first()
        if user is not None:
            return link_google_account(request, user, google_sub)

        existing = User.objects.filter(email__iexact=email).first()
        if existing is not None:
            return link_google_account(request, existing, google_sub)

        try:
            with transaction.atomic():
                user = User(
                    username=email,
                    email=email,
                    first_name=pending.get('first_name', ''),
                    last_name=pending.get('last_name', ''),
                    role=User.Role.CLIENT,
                    google_sub=google_sub,
                    accepted_terms_at=timezone.now(),
                    terms_version=settings.TERMS_VERSION,
                )
                user.set_unusable_password()
                user.save()
        except IntegrityError:
            user = User.objects.filter(google_sub=google_sub).first()
            if user is None:
                user = User.objects.filter(email__iexact=email).first()
            if user is None:
                messages.error(request, GOOGLE_LOGIN_ERROR)
                return redirect('users:login')
            return link_google_account(request, user, google_sub)

        clear_google_pending(request)
        try:
            GmailService.send_registration_confirmation(user, request)
        except GmailServiceError:
            pass
        return login_google_user(request, user)
