from urllib.parse import urlencode

import requests
from django.conf import settings

GOOGLE_AUTHORIZATION_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_URL = 'https://openidconnect.googleapis.com/v1/userinfo'
GOOGLE_SCOPES = ('openid', 'email', 'profile')
GOOGLE_HTTP_TIMEOUT = 10


class GoogleOAuthError(RuntimeError):
    pass


class GoogleOAuthNotConfigured(GoogleOAuthError):
    pass


def is_configured():
    return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)


def build_authorization_url(redirect_uri, state):
    if not is_configured():
        raise GoogleOAuthNotConfigured('La autenticación con Google no está configurada.')
    params = {
        'client_id': settings.GOOGLE_CLIENT_ID,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': ' '.join(GOOGLE_SCOPES),
        'state': state,
        'access_type': 'online',
        'prompt': 'select_account',
    }
    return f'{GOOGLE_AUTHORIZATION_URL}?{urlencode(params)}'


def exchange_code(code, redirect_uri):
    try:
        response = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                'client_id': settings.GOOGLE_CLIENT_ID,
                'client_secret': settings.GOOGLE_CLIENT_SECRET,
                'code': code,
                'grant_type': 'authorization_code',
                'redirect_uri': redirect_uri,
            },
            timeout=GOOGLE_HTTP_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        raise GoogleOAuthError('No pudimos validar la cuenta de Google.') from error

    try:
        data = response.json()
    except ValueError as error:
        raise GoogleOAuthError('Google devolvió una respuesta inválida.') from error

    access_token = data.get('access_token')
    if not access_token:
        raise GoogleOAuthError('Google no devolvió un token de acceso.')
    return access_token


def fetch_userinfo(access_token):
    try:
        response = requests.get(
            GOOGLE_USERINFO_URL,
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=GOOGLE_HTTP_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        raise GoogleOAuthError('No pudimos obtener los datos de Google.') from error

    try:
        data = response.json()
    except ValueError as error:
        raise GoogleOAuthError('Google devolvió una respuesta inválida.') from error

    if not data.get('sub') or not data.get('email'):
        raise GoogleOAuthError('La cuenta de Google no tiene un correo disponible.')
    if data.get('email_verified') not in (True, 'true'):
        raise GoogleOAuthError('La cuenta de Google no tiene el correo verificado.')
    return data
