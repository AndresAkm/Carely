from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .base import (
    CheckoutSession,
    GatewayConnectionError,
    GatewayError,
    GatewayInvalidResponseError,
    GatewayNotConfiguredError,
    GatewayRedirectBlockedError,
    GatewayStatus,
    GatewayTransaction,
    GatewayTransactionNotFoundError,
    PaymentGateway,
    to_cents,
)
from .simulated import SimulatedGateway
from .wompi import WompiGateway

GATEWAYS = {
    WompiGateway.slug: WompiGateway,
    SimulatedGateway.slug: SimulatedGateway,
}


def get_gateway_class():
    slug = (getattr(settings, 'PAYMENT_GATEWAY', 'wompi') or 'wompi').strip().lower()
    try:
        return GATEWAYS[slug]
    except KeyError as error:
        raise ImproperlyConfigured(
            f'PAYMENT_GATEWAY="{slug}" no corresponde a ninguna pasarela registrada.'
        ) from error


def get_gateway():
    return get_gateway_class()()


__all__ = [
    'CheckoutSession',
    'GatewayConnectionError',
    'GatewayError',
    'GatewayInvalidResponseError',
    'GatewayNotConfiguredError',
    'GatewayRedirectBlockedError',
    'GatewayStatus',
    'GatewayTransaction',
    'GatewayTransactionNotFoundError',
    'GATEWAYS',
    'PaymentGateway',
    'SimulatedGateway',
    'WompiGateway',
    'get_gateway',
    'get_gateway_class',
    'to_cents',
]