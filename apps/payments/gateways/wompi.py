"""
Cliente y pasarela de Wompi (Colombia).

Referencia de la API: https://docs.wompi.co/docs/colombia/transacciones/

- El checkout se abre en `https://checkout.wompi.co/p/` con un formulario GET.
  La firma de integridad ata referencia, monto y moneda, de modo que la URL no
  se puede reutilizar para cobrar otra cantidad.
- El estado se consulta en `GET {WOMPI_API_URL}/transactions/{id}`, que desde
  la actualización de la API exige llave privada y responde 404 sin ella.
- Los eventos llegan a un webhook con el checksum en `X-Event-Checksum` y en
  `signature.checksum`.

Nada de lo que se guarda aquí incluye datos de tarjeta: la pasarela nunca los
entrega y el backend no los pide.
"""

import hashlib
import hmac
import ipaddress
from urllib.parse import urlencode, urlparse

import requests

from django.conf import settings

from .base import (
    CheckoutSession,
    GatewayConnectionError,
    GatewayInvalidResponseError,
    GatewayNotConfiguredError,
    GatewayRedirectBlockedError,
    GatewayStatus,
    GatewayTransaction,
    GatewayTransactionNotFoundError,
    PaymentGateway,
    to_cents,
)

WOMPI_STATUS_MAP = {
    'PENDING': PaymentGateway.STATUS_PENDING,
    'APPROVED': PaymentGateway.STATUS_APPROVED,
    'DECLINED': PaymentGateway.STATUS_DECLINED,
    'VOIDED': PaymentGateway.STATUS_VOIDED,
    'ERROR': PaymentGateway.STATUS_ERROR,
}

#: Claves que se descartan de la respuesta antes de guardarla.
SENSITIVE_RESPONSE_KEYS = frozenset({
    'token',
    'card_number',
    'cvv',
    'cvc',
    'password',
    'acceptance_token',
    'signature',
})


def build_integrity_signature(reference, amount_in_cents, currency, integrity_secret):
    """
    SHA256 de `<referencia><monto en centavos><moneda><secreto de integridad>`.

    El orden importa y Wompi no publica el algoritmo con otro nombre: es el
    mismo que usan el widget, el web checkout y el POST /transactions.
    """
    concatenated = f'{reference}{amount_in_cents}{currency}{integrity_secret}'
    return hashlib.sha256(concatenated.encode('utf-8')).hexdigest()


def compute_event_checksum(payload, events_secret):
    """
    Reproduce el checksum de un evento.

    Wompi lista en `signature.properties` los campos que se firman y el orden
    en que se concatenan, así que nunca se puede asumir una lista fija: hay que
    leerla del evento. Luego se añade el timestamp y el secreto de eventos.
    """
    signature = payload.get('signature')
    if not isinstance(signature, dict):
        raise GatewayInvalidResponseError('El evento no trae bloque de firma.')

    properties = signature.get('properties')
    if not isinstance(properties, list) or not properties:
        raise GatewayInvalidResponseError('El evento no declara las propiedades firmadas.')

    # Wompi firma rutas relativas a `data` (por ejemplo `transaction.id`
    # cuando el valor vive en `data.transaction.id`), no a la raíz del evento.
    signed_data = payload.get('data')
    if not isinstance(signed_data, dict):
        raise GatewayInvalidResponseError('El evento no trae el bloque de datos firmado.')

    parts = [_resolve_property(signed_data, prop) for prop in properties]
    parts.append(signature.get('timestamp', ''))
    parts.append(events_secret)
    return hashlib.sha256(''.join(str(part) for part in parts).encode('utf-8')).hexdigest()


def _resolve_property(signed_data, path):
    """Lee un valor del bloque firmado siguiendo una ruta con puntos."""
    current = signed_data
    for key in str(path).split('.'):
        if not isinstance(current, dict) or key not in current:
            raise GatewayInvalidResponseError(f'El evento no trae el dato firmado "{path}".')
        current = current[key]
    return current


def safe_metadata(data):
    """Deja solo los campos no sensibles que hacen falta para auditar el cobro."""
    return {
        key: value
        for key, value in (data or {}).items()
        if key not in SENSITIVE_RESPONSE_KEYS
    }


# ─────────────────────────────────────────────────────────────────────────────
# URL de retorno
# ─────────────────────────────────────────────────────────────────────────────

#: Nombres que nunca apuntan a un servidor real alcanzable desde internet.
#: `testserver` entra porque Django lo usa como host por defecto en los tests:
#: aceptarlo haría que un test "pasara" con una URL que en producción fallaría.
PRIVATE_HOSTNAMES = frozenset({
    'localhost',
    'testserver',
    '',
})

#: Sufijos reservados para redes locales o de pruebas.
PRIVATE_HOST_SUFFIXES = ('.localhost', '.local', '.internal', '.test', '.invalid')

#: Redes que nunca son alcanzables desde internet. El WAF de CloudFront delante
#: del checkout de Wompi las rechaza con un 403 genérico, sin explicar el motivo.
PRIVATE_NETWORKS = tuple(
    ipaddress.ip_network(cidr)
    for cidr in (
        '127.0.0.0/8',      # loopback
        '10.0.0.0/8',       # privada clase A
        '172.16.0.0/12',    # privada clase B
        '192.168.0.0/16',   # privada clase C
        '169.254.0.0/16',   # link-local
        '::1/128',          # loopback IPv6
        'fc00::/7',         # única local IPv6
        'fe80::/10',        # link-local IPv6
    )
)


def is_publicly_routable(host):
    """
    ¿ese host se puede alcanzar desde internet?

    Se decide sin resolver DNS a propósito: una consulta en cada intento de pago
    añade latencia y puede fallar por motivos que no tienen que ver con la
    pasarela. Un nombre que no es una IP literal se juzga por su forma.
    """
    host = (host or '').strip().lower().rstrip('.')
    if not host:
        return False

    # Un host IPv6 literal llega entre corchetes: `[::1]`.
    bare = host[1:-1] if host.startswith('[') and host.endswith(']') else host

    try:
        address = ipaddress.ip_address(bare)
    except ValueError:
        pass
    else:
        # Un `ip_address` nunca es alcanzable si cae en estas redes. Los
        # reservados como `0.0.0.0` o los multicast también se quedan fuera.
        return not (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
        )

    if bare in PRIVATE_HOSTNAMES:
        return False
    return not bare.endswith(PRIVATE_HOST_SUFFIXES)


def assert_public_redirect_url(redirect_url):
    """
    Falla si Wompi no aceptaría la URL de retorno.

    La comprobación es local y previa a firmar. Si se dejara pasar, Wompi
    responde 403 desde CloudFront y el usuario ve "Request blocked" sin ninguna
    pista de que el problema es la URL, no su tarjeta ni el pago.
    """
    if is_publicly_routable(urlparse(redirect_url or '').hostname):
        return

    raise GatewayRedirectBlockedError(
        'Wompi solo acepta pagos si el sitio tiene una dirección pública. '
        'Desde localhost esto no funciona: publica la aplicación en un dominio '
        'accesible desde internet, o expónla con un túnel como Cloudflare Tunnel '
        'o ngrok, y vuelve a intentar el pago. Tu pedido quedó creado.'
    )


class WompiClient:
    """Acceso HTTP a la API de Wompi. Solo se usa desde el backend."""

    def __init__(self, base_url=None, private_key=None, timeout=None):
        self.base_url = (base_url or settings.WOMPI_API_URL).rstrip('/')
        self.private_key = private_key if private_key is not None else settings.WOMPI_PRIVATE_KEY
        self.timeout = timeout if timeout is not None else settings.WOMPI_HTTP_TIMEOUT

    def _headers(self):
        if not self.private_key:
            raise GatewayNotConfiguredError('Falta configurar WOMPI_PRIVATE_KEY.')
        return {
            'Accept': 'application/json',
            'Authorization': f'Bearer {self.private_key}',
            'Content-Type': 'application/json',
        }

    def _request(self, method, path):
        url = f'{self.base_url}/{path.lstrip("/")}'
        try:
            response = requests.request(
                method,
                url,
                headers=self._headers(),
                timeout=self.timeout,
            )
        except requests.RequestException as error:
            raise GatewayConnectionError(
                'No pudimos comunicarnos con la pasarela de pago. Intenta de nuevo en unos minutos.'
            ) from error

        if response.status_code == 404:
            raise GatewayTransactionNotFoundError('La pasarela no conoce esa transacción.')
        if response.status_code >= 400:
            raise GatewayInvalidResponseError(
                self._describe_error(response) or 'La pasarela rechazó la consulta.'
            )

        try:
            body = response.json()
        except ValueError as error:
            raise GatewayInvalidResponseError('La pasarela devolvió una respuesta ilegible.') from error

        data = body.get('data') if isinstance(body, dict) else None
        if not isinstance(data, dict):
            raise GatewayInvalidResponseError('La pasarela no devolvió los datos de la transacción.')
        return data

    @staticmethod
    def _describe_error(response):
        try:
            body = response.json()
        except ValueError:
            return None
        errors = body.get('error') if isinstance(body, dict) else None
        if isinstance(errors, dict):
            return errors.get('message') or errors.get('type')
        return None

    def get_transaction(self, transaction_id):
        if not transaction_id:
            raise GatewayTransactionNotFoundError('Falta el identificador de la transacción.')
        return self._request('GET', f'transactions/{transaction_id}')


class WompiGateway(PaymentGateway):
    slug = 'wompi'

    def __init__(self, client=None):
        self._client = client

    @property
    def client(self):
        return self._client or WompiClient()

    def is_ready(self):
        return all([
            settings.WOMPI_PUBLIC_KEY,
            settings.WOMPI_PRIVATE_KEY,
            settings.WOMPI_INTEGRITY_SECRET,
            settings.WOMPI_EVENTS_SECRET,
            settings.WOMPI_API_URL,
        ])

    def create_checkout(self, *, reference, amount, currency, customer_email,
                        redirect_url, customer_data=None):
        if not self.is_ready():
            raise GatewayNotConfiguredError('La pasarela de pago no está configurada.')

        assert_public_redirect_url(redirect_url)

        amount_in_cents = to_cents(amount)
        params = {
            'public-key': settings.WOMPI_PUBLIC_KEY,
            'currency': currency,
            'amount-in-cents': str(amount_in_cents),
            'reference': reference,
            'signature:integrity': build_integrity_signature(
                reference,
                amount_in_cents,
                currency,
                settings.WOMPI_INTEGRITY_SECRET,
            ),
            'redirect-url': redirect_url,
            'customer-data:email': customer_email,
        }
        for key, value in (customer_data or {}).items():
            if value:
                params[f'customer-data:{key}'] = value

        checkout_url = settings.WOMPI_CHECKOUT_URL
        separator = '&' if '?' in checkout_url else '?'
        return CheckoutSession(
            redirect_url=f'{checkout_url}{separator}{urlencode(params)}',
            reference=reference,
        )

    def fetch_transaction(self, transaction_id, *, reference='', amount_in_cents=None):
        data = self.client.get_transaction(transaction_id)
        return self._to_transaction(data)

    def parse_event(self, payload):
        data = (payload.get('data') or {}).get('transaction')
        if not isinstance(data, dict):
            raise GatewayInvalidResponseError('El evento no trae la transacción afectada.')
        return self._to_transaction(data)

    def verify_event(self, payload, checksum):
        if not settings.WOMPI_EVENTS_SECRET:
            raise GatewayNotConfiguredError('Falta configurar WOMPI_EVENTS_SECRET.')
        expected = compute_event_checksum(payload, settings.WOMPI_EVENTS_SECRET)
        provided = checksum or (payload.get('signature') or {}).get('checksum')
        if not provided:
            return False
        return hmac.compare_digest(expected.lower(), str(provided).lower())

    @staticmethod
    def _to_transaction(data):
        raw_status = str(data.get('status') or '').upper()
        code = WOMPI_STATUS_MAP.get(raw_status, PaymentGateway.STATUS_ERROR)
        return GatewayTransaction(
            transaction_id=data.get('id') or '',
            reference=data.get('reference') or '',
            status=_to_status(code, data.get('status_message')),
            amount_in_cents=_to_int(data.get('amount_in_cents')),
            currency=data.get('currency') or '',
            payment_method_type=data.get('payment_method_type') or '',
            metadata=safe_metadata({
                'payment_method_type': data.get('payment_method_type') or '',
                'status_message': data.get('status_message') or '',
                'amount_in_cents': _to_int(data.get('amount_in_cents')),
            }),
        )


def _to_status(code, message=''):
    return GatewayStatus(
        code=code,
        is_final=code in PaymentGateway.FINAL_STATUSES,
        is_approved=code == PaymentGateway.STATUS_APPROVED,
        message=str(message or '')[:255],
    )


def _to_int(value):
    """
    Lee un entero de la respuesta de Wompi sin inventarlo.

    Devolver `0` cuando el dato falta sería peligroso: el servicio compara el
    monto contra el pago guardado, así que un cero silencioso se vería como un
    cobro de $0 y descartaría el evento sin avisar.
    """
    if value is None or value == '':
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise GatewayInvalidResponseError(
            f'La pasarela devolvió un monto inválido: {value!r}'
        ) from error