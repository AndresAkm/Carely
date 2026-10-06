import os
import secrets
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured

import pymysql

pymysql.install_as_MySQLdb()

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def load_env_file(path):
    if not path.exists():
        return
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        os.environ.setdefault(key, value)


load_env_file(BASE_DIR / '.env')

SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    secrets.token_urlsafe(50),
)

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.admindocs',
    'rest_framework',
    'drf_spectacular',
    'apps.core',
    'apps.catalog',
    'apps.users',
    'apps.inventory',
    'apps.cart',
    'apps.orders',
    'apps.payments'
]

MIDDLEWARE = [
    # Va primero para poder interceptar las respuestas 403/404 de todo el
    # sitio y pintarlas con las plantillas de Carely aun con DEBUG=True.
    'apps.core.middleware.CarelyErrorPagesMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.core.context_processors.site_settings',
                'apps.core.context_processors.footer_categories',
                'apps.core.context_processors.cart_count',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DB_HOST = os.environ.get('DJANGO_DB_HOST', '').strip()

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DJANGO_DB_NAME', 'carely'),
        'USER': os.environ.get('DJANGO_DB_USER', ''),
        'PASSWORD': os.environ.get('DJANGO_DB_PASSWORD', ''),
        'HOST': DB_HOST,
        'PORT': os.environ.get('DJANGO_DB_PORT', '3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

REST_FRAMEWORK = {

    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",

    "DEFAULT_AUTHENTICATION_CLASSES": (

        "rest_framework.authentication.SessionAuthentication",
        
        "rest_framework.authentication.BasicAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",

    ),

    "DEFAULT_PERMISSION_CLASSES": (

        "rest_framework.permissions.IsAuthenticatedOrReadOnly",

    ),

}

LANGUAGE_CODE = 'es'

TIME_ZONE = 'America/Bogota'

USE_I18N = True

USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

SUPABASE_URL = os.environ.get('SUPABASE_URL', '').rstrip('/')
SUPABASE_S3_ACCESS_KEY_ID = os.environ.get('SUPABASE_S3_ACCESS_KEY_ID', '')
SUPABASE_S3_SECRET_ACCESS_KEY = os.environ.get('SUPABASE_S3_SECRET_ACCESS_KEY', '')
SUPABASE_STORAGE_BUCKET = os.environ.get('SUPABASE_STORAGE_BUCKET', '')

if all((SUPABASE_URL, SUPABASE_S3_ACCESS_KEY_ID, SUPABASE_S3_SECRET_ACCESS_KEY, SUPABASE_STORAGE_BUCKET)):
    supabase_host = urlparse(SUPABASE_URL).netloc
    AWS_S3_ENDPOINT_URL = f'https://{supabase_host.replace(".supabase.co", ".storage.supabase.co")}/storage/v1/s3'
    AWS_ACCESS_KEY_ID = SUPABASE_S3_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY = SUPABASE_S3_SECRET_ACCESS_KEY
    AWS_STORAGE_BUCKET_NAME = SUPABASE_STORAGE_BUCKET
    AWS_S3_REGION_NAME = 'us-east-1'
    AWS_S3_ADDRESSING_STYLE = 'path'
    AWS_S3_SIGNATURE_VERSION = 's3v4'
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = False
    AWS_S3_FILE_OVERWRITE = False
    AWS_S3_CUSTOM_DOMAIN = f'{supabase_host}/storage/v1/object/public/{SUPABASE_STORAGE_BUCKET}'
    STORAGES = {
        'default': {
            'BACKEND': 'storages.backends.s3.S3Storage',
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    }

LOGIN_URL = 'users:login'
LOGIN_REDIRECT_URL = 'core:dashboard'
LOGOUT_REDIRECT_URL = 'core:home'

AUTH_USER_MODEL = 'users.User'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

SPECTACULAR_SETTINGS = {
    'TITLE': 'Carely API',
    'DESCRIPTION': (
        'API REST del e-commerce Carely. '
        'Catálogo de productos de cuidado personal, carrito de compras, '
        'pedidos, pagos y gestión de inventario.'
    ),
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'CONTACT': {
        'name': 'Carely Soporte',
        'email': 'soporte@carely.com',
        'url': 'https://carely.com',
    },
    'LICENSE': {
        'name': 'MIT',
        'url': 'https://opensource.org/licenses/MIT',
    },
    'TAGS': [
        {'name': 'Catálogo', 'description': 'Productos y categorías'},
        {'name': 'Carrito', 'description': 'Carrito de compras'},
        {'name': 'Pedidos', 'description': 'Gestión de pedidos'},
        {'name': 'Pagos', 'description': 'Procesamiento de pagos'},
        {'name': 'Inventario', 'description': 'Control de inventario'},
        {'name': 'Usuarios', 'description': 'Gestión de usuarios'},
    ],
    'EXTERNAL_DOCS': {
        'description': 'Repositorio del proyecto',
        'url': 'https://github.com/carely/carely-django',
    },
    'SORT_OPERATIONS': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'ENUM_NAME_OVERRIDES': {
        'RoleEnum': 'apps.users.models.User.Role',
        'MovementTypeEnum': 'apps.inventory.models.InventoryMovement.MovementType',
        'OrderStatusEnum': 'apps.orders.models.Order.Status',
        'PaymentMethodEnum': 'apps.payments.models.Payment.PaymentMethod',
        'PaymentStatusEnum': 'apps.payments.models.Payment.Status',
    },
}

SIMPLE_JWT = {
    'AUTH_HEADER_TYPES': ('Bearer',),
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': False,
}

EMAIL_BACKEND = os.environ.get(
    'DJANGO_EMAIL_BACKEND',
    'django.core.mail.backends.smtp.EmailBackend',
)
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '25'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'true').lower() in {'1', 'true', 'yes', 'on'}
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', 'false').lower() in {'1', 'true', 'yes', 'on'}
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'no-reply@carely.com')
PASSWORD_RESET_TIMEOUT = 3600

# Vigencia del enlace de reactivación que se envía al deshabilitar una cuenta.
ACCOUNT_REACTIVATION_TIMEOUT = int(os.environ.get('ACCOUNT_REACTIVATION_TIMEOUT', 604800))

# Verificación en dos pasos por código de un solo uso enviado al correo.
TWO_FACTOR_CODE_LENGTH = int(os.environ.get('TWO_FACTOR_CODE_LENGTH', 6))
TWO_FACTOR_CODE_TTL = int(os.environ.get('TWO_FACTOR_CODE_TTL', 600))
TWO_FACTOR_MAX_ATTEMPTS = int(os.environ.get('TWO_FACTOR_MAX_ATTEMPTS', 5))

# ── Datos públicos de la tienda (footer, legal, emails) ──────────────────────
SITE_NAME = os.environ.get('CARELY_SITE_NAME', 'Carely')
SITE_DESCRIPTION = os.environ.get(
    'CARELY_SITE_DESCRIPTION',
    'Tu tienda de cuidado personal de confianza',
)

# Versión de los términos y condiciones. Súbela cuando cambien los textos
# legales para poder distinguir qué versión aceptó cada usuario.
TERMS_VERSION = os.environ.get('CARELY_TERMS_VERSION', '2026-01-01')

# Fecha visible en la página legal para que coincida con TERMS_VERSION.
TERMS_EFFECTIVE_DATE = os.environ.get(
    'CARELY_TERMS_EFFECTIVE_DATE',
    '1 de enero de 2026',
)

CARELY_EMAIL = os.environ.get('CARELY_EMAIL', 'carelywebsite@gmail.com')
CARELY_PHONE = os.environ.get('CARELY_PHONE', '+57 323 227 3483')
CARELY_PHONE_HREF = os.environ.get('CARELY_PHONE_HREF', '+573232273483')
CARELY_ADDRESS = os.environ.get('CARELY_ADDRESS', 'Medellín, Colombia')
CARELY_SOCIALS = {
    'facebook': os.environ.get('CARELY_SOCIAL_FACEBOOK', ''),
    'instagram': os.environ.get('CARELY_SOCIAL_INSTAGRAM', ''),
    'whatsapp': os.environ.get('CARELY_SOCIAL_WHATSAPP', ''),
}

# ── Pasarela de pagos (Wompi) ─────────────────────────────────────────────────
# El ambiente se elige con WOMPI_API_URL y las llaves deben coincidir con él:
# sandbox usa pub_test_/prv_test_ y producción pub_prod_/prv_prod_.
WOMPI_PUBLIC_KEY = os.environ.get('WOMPI_PUBLIC_KEY', '')
# Solo backend. Nunca se expone en templates, serializer ni respuestas JSON.
WOMPI_PRIVATE_KEY = os.environ.get('WOMPI_PRIVATE_KEY', '')
WOMPI_API_URL = os.environ.get('WOMPI_API_URL', 'https://sandbox.wompi.co/v1')
WOMPI_CHECKOUT_URL = os.environ.get('WOMPI_CHECKOUT_URL', 'https://checkout.wompi.co/p/')
# Secreto de integridad (prefijo test_integrity_ o prod_integrity_). Firma el
# monto y la referencia para que Wompi no acepte cantidades alteradas.
WOMPI_INTEGRITY_SECRET = os.environ.get('WOMPI_INTEGRITY_SECRET', '')
# Secreto de eventos (prefijo test_events_ o prod_events_). Valida el checksum
# de los webhooks. Es distinto de la llave privada.
WOMPI_EVENTS_SECRET = os.environ.get('WOMPI_EVENTS_SECRET', '')
WOMPI_CURRENCY = os.environ.get('WOMPI_CURRENCY', 'COP')
WOMPI_HTTP_TIMEOUT = int(os.environ.get('WOMPI_HTTP_TIMEOUT', 15))

# Pasarela activa: 'wompi' para la integración real, 'simulado' para desarrollo
# y pruebas sin salir a internet. Cambiarla no requiere tocar el código.
PAYMENT_GATEWAY = os.environ.get('PAYMENT_GATEWAY', 'wompi')
