"""
Contrato común de las pasarelas de pago.

`PaymentService` habla con este contrato y nunca con Wompi directamente: para
cambiar de pasarela basta con registrar otra implementación en
`gateways/__init__.py` y cambiar `PAYMENT_GATEWAY`.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal


class GatewayError(Exception):
    """Fallo genérico de la pasarela, ya traducido al usuario."""


class GatewayNotConfiguredError(GatewayError):
    """Faltan llaves o URLs de la pasarela en el entorno."""


class GatewayRedirectBlockedError(GatewayError):
    """
    La pasarela no aceptaría la URL de retorno porque no es pública.

    Existe porque el fallo no se puede dejar para que lo reporte la pasarela:
    Wompi responde un 403 de CloudFront sin explicar qué está mal, y el
    usuario solo ve "Request blocked". Rechazarlo aquí permite decir qué hacer.
    """


class GatewayConnectionError(GatewayError):
    """No hubo respuesta: red caída, timeout o DNS."""


class GatewayInvalidResponseError(GatewayError):
    """La pasarela respondió algo que no se puede interpretar."""


class GatewayTransactionNotFoundError(GatewayError):
    """La pasarela no conoce la transacción consultada."""


def to_cents(amount: Decimal) -> int:
    """Convierte un monto en pesos a centavos enteros, como los pide Wompi."""
    return int((Decimal(str(amount)) * 100).to_integral_value())


class PaymentGateway(ABC):
    """
    Interfaz que toda pasarela debe cumplir.

    Hereda de `ABC` para que un gateway a medio escribir falle al instanciarse
    en vez de romperse en producción cuando le toque una llamada.
    """

    STATUS_PENDING = 'pendiente'
    STATUS_APPROVED = 'aprobado'
    STATUS_DECLINED = 'rechazado'
    STATUS_VOIDED = 'anulado'
    STATUS_ERROR = 'error'

    #: Estados en los que la pasarela ya no va a cambiar de veredicto.
    FINAL_STATUSES = frozenset({STATUS_APPROVED, STATUS_DECLINED, STATUS_VOIDED})

    #: Estados de Wompi que no son un veredicto y que no se traducen.
    UNKNOWN_STATUS = 'desconocido'

    slug = ''

    @abstractmethod
    def is_ready(self) -> bool:
        """True si la pasarela tiene todo lo necesario para operar."""

    @abstractmethod
    def create_checkout(self, *, reference, amount, currency, customer_email,
                        redirect_url, customer_data=None):
        """
        Prepara el pago en la pasarela y devuelve la sesión de checkout.

        `amount` llega en pesos y se convierte aquí; quien llama no decide el
        monto que ve la pasarela más que el backend.
        """

    @abstractmethod
    def fetch_transaction(self, transaction_id, *, reference='', amount_in_cents=None):
        """
        Consulta el estado real de una transacción ya creada.

        `reference` y `amount_in_cents` son lo que el backend ya tiene guardado
        para ese pago. Una pasarela real los ignora y responde con su propia
        verdad; una simulada los devuelve tal cual para poder probar el flujo sin
        red. El servicio compara ambos.
        """

    @abstractmethod
    def parse_event(self, payload):
        """Traduce el cuerpo de un evento a la transacción que menciona."""

    @abstractmethod
    def verify_event(self, payload, checksum) -> bool:
        """Valida que un evento provenga de la pasarela y no esté alterado."""


@dataclass(frozen=True)
class GatewayStatus:
    code: str
    is_final: bool
    is_approved: bool
    message: str = ''


@dataclass(frozen=True)
class CheckoutSession:
    redirect_url: str
    reference: str


@dataclass(frozen=True)
class GatewayTransaction:
    transaction_id: str
    reference: str
    status: GatewayStatus
    amount_in_cents: int
    currency: str = ''
    payment_method_type: str = ''
    metadata: dict = field(default_factory=dict)