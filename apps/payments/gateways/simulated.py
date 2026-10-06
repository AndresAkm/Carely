"""
Pasarela simulada, para desarrollo y pruebas sin red.

No habla con Wompi: devuelve un resultado local y acepta eventos sin checksum.
Sirve para probar el flujo completo (crear pago, confirmar, consultar estado)
dejando las URLs y los secretos vacíos. La integración real se elige con
`PAYMENT_GATEWAY=wompi`.
"""

from django.urls import reverse

from .base import (
    CheckoutSession,
    GatewayStatus,
    GatewayTransaction,
    PaymentGateway,
    to_cents,
)


class SimulatedGateway(PaymentGateway):
    slug = 'simulado'

    #: Estado que devuelve la pasarela simulada. Se puede forzar por instancia
    #: para probar el camino de pago rechazado sin tocar el código.
    default_status = PaymentGateway.STATUS_APPROVED

    def __init__(self, status=None):
        self.status = status or self.default_status

    def is_ready(self):
        return True

    def create_checkout(self, *, reference, amount, currency, customer_email,
                        redirect_url, customer_data=None):
        url = reverse('payments:simulated', kwargs={'reference': reference})
        return CheckoutSession(redirect_url=url, reference=reference)

    def fetch_transaction(self, transaction_id, *, reference='', amount_in_cents=None):
        return GatewayTransaction(
            transaction_id=transaction_id,
            reference=reference,
            status=_status(self.status),
            amount_in_cents=amount_in_cents,
            currency='COP',
            payment_method_type='SIMULATED',
        )

    def parse_event(self, payload):
        data = (payload.get('data') or {}).get('transaction') or {}
        return GatewayTransaction(
            transaction_id=data.get('id') or '',
            reference=data.get('reference') or '',
            status=_status(data.get('status') or self.status),
            amount_in_cents=data.get('amount_in_cents'),
            currency=data.get('currency') or 'COP',
            payment_method_type='SIMULATED',
        )

    def verify_event(self, payload, checksum):
        return True


#: Traduce los estados en mayúsculas de Wompi a los normalizados del contrato,
#: para que un evento con forma de Wompi se pueda probar sin backend configurado.
STATUS_BY_WOMPI_CODE = {
    'PENDING': PaymentGateway.STATUS_PENDING,
    'APPROVED': PaymentGateway.STATUS_APPROVED,
    'DECLINED': PaymentGateway.STATUS_DECLINED,
    'REJECTED': PaymentGateway.STATUS_DECLINED,
    'VOIDED': PaymentGateway.STATUS_VOIDED,
    'ERROR': PaymentGateway.STATUS_ERROR,
}


def _status(code):
    normalized = STATUS_BY_WOMPI_CODE.get(str(code).upper(), code)
    return GatewayStatus(
        code=normalized,
        is_final=normalized in PaymentGateway.FINAL_STATUSES,
        is_approved=normalized == PaymentGateway.STATUS_APPROVED,
        message='Resultado simulado por la pasarela de desarrollo.',
    )