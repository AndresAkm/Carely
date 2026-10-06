"""
Orquesta de pagos. Es la única capa que conoce el modelo `Payment`.

No sabe cómo es Wompi por dentro: pide la preparación del checkout a la pasarela
activa, le aplica el estado que devuelve y refleja ese estado en el pedido.
Cambiar de pasarela no obliga a tocar este archivo.
"""

import logging

from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.urls import reverse

from apps.orders.models import Order, OrderStatusHistory
from apps.payments.gateways import get_gateway, get_gateway_class, to_cents
from apps.payments.gateways.base import PaymentGateway
from apps.payments.models import Payment


logger = logging.getLogger(__name__)

#: Evento de Wompi que significa "la transacción cambió de estado".
TRANSACTION_UPDATED_EVENT = 'transaction.updated'

GATEWAY_STATUS_MAP = {
    PaymentGateway.STATUS_PENDING: Payment.Status.PENDIENTE,
    PaymentGateway.STATUS_APPROVED: Payment.Status.APROBADO,
    PaymentGateway.STATUS_DECLINED: Payment.Status.RECHAZADO,
    PaymentGateway.STATUS_VOIDED: Payment.Status.ANULADO,
    PaymentGateway.STATUS_ERROR: Payment.Status.ERROR,
}

#: `payment_method_type` de Wompi a `Payment.PaymentMethod`.
PAYMENT_METHOD_MAP = {
    'CARD': Payment.PaymentMethod.CARD,
    'PSE': Payment.PaymentMethod.PSE,
    'NEQUI': Payment.PaymentMethod.NEQUI,
    'BANCOLOMBIA_TRANSFER': Payment.PaymentMethod.BANCOLOMBIA_TRANSFER,
    'BANCOLOMBIA_COLLECT': Payment.PaymentMethod.BANCOLOMBIA_TRANSFER,
    'DAVIPLATA': Payment.PaymentMethod.DAVIPLATA,
    'CASH': Payment.PaymentMethod.EFECTIVO,
}

#: Un pago en alguno de estos estados bloquea la creación de otro para el pedido.
ACTIVE_STATUSES = (Payment.Status.PENDIENTE, Payment.Status.APROBADO)


class PaymentError(Exception):
    """Fallo de negocio del proceso de pago, con mensaje para el usuario."""


class PaymentAlreadyExistsError(PaymentError):
    pass


class PaymentNotFoundError(PaymentError):
    pass


class InvalidAmountError(PaymentError):
    pass


class InvalidStatusError(PaymentError):
    pass


class InvalidEventError(PaymentError):
    pass


def find_by_reference(reference):
    return Payment.objects.filter(reference=reference).first()


def find_active_payment(order):
    return Payment.objects.filter(order=order, status__in=ACTIVE_STATUSES).first()


class PaymentService:
    @staticmethod
    def create_payment(order, method=Payment.PaymentMethod.CARD) -> Payment:
        """
        Abre un pago pendiente para un pedido.

        El monto sale siempre de `order.total`. No acepta monto de entrada a
        propósito: es la forma más barata de que el frontend no pueda elegir
        cuánto se cobra.
        """
        amount = Decimal(str(order.total)).quantize(Decimal('0.01'))
        if amount <= Decimal('0.00'):
            raise InvalidAmountError('El pedido no tiene un total válido para cobrar.')

        if find_active_payment(order) is not None:
            raise PaymentAlreadyExistsError('Este pedido ya tiene un pago en curso.')

        return Payment.objects.create(
            order=order,
            gateway=get_gateway_class().slug,
            amount=amount,
            payment_method=method,
            status=Payment.Status.PENDIENTE,
        )

    @staticmethod
    def start_checkout(payment, request, customer_data=None) -> str:
        """
        Devuelve la URL a la que hay que mandar al cliente para que pague.

        El monto, la referencia y la firma salen del pago ya guardado, así que
        lo que se manda a la pasarela es exactamente lo que se cobró.
        """
        gateway = get_gateway()
        redirect_url = request.build_absolute_uri(
            reverse('payments:return_page', args=[payment.pk]),
        )
        session = gateway.create_checkout(
            reference=payment.reference,
            amount=payment.amount,
            currency=settings.WOMPI_CURRENCY,
            customer_email=payment.order.user.email,
            redirect_url=redirect_url,
            customer_data=customer_data or {'full-name': request.user.get_full_name()},
        )
        return session.redirect_url

    @staticmethod
    def sync_with_gateway(payment, gateway=None) -> Payment:
        """Consulta a la pasarela el estado real de la transacción."""
        gateway = gateway or get_gateway()
        if not payment.transaction_id:
            raise PaymentError('El pago todavía no tiene una transacción en la pasarela.')
        data = gateway.fetch_transaction(
            payment.transaction_id,
            reference=payment.reference,
            amount_in_cents=to_cents(payment.amount),
        )
        return PaymentService.apply_gateway_status(
            payment,
            data.status,
            transaction_id=data.transaction_id,
            metadata=data.metadata,
            amount_in_cents=data.amount_in_cents,
        )

    @staticmethod
    def handle_event(payload, checksum='', gateway=None) -> Payment:
        """
        Procesa un evento de la pasarela.

        Es idempotente: el mismo evento repetido no vuelve a tocar el pedido,
        porque `apply_gateway_status` ignora pagos que ya están en un estado
        final y el pedido solo se confirma una vez.
        """
        gateway = gateway or get_gateway()

        if not gateway.verify_event(payload, checksum):
            raise InvalidEventError('La firma del evento no es válida.')

        event_name = payload.get('event')
        if event_name != TRANSACTION_UPDATED_EVENT:
            raise PaymentError(
                f'Evento ignorado, no es una actualización de transacción: {event_name}'
            )

        data = gateway.parse_event(payload)
        payment = find_by_reference(data.reference)
        if payment is None:
            raise PaymentNotFoundError(
                f'Recibimos un evento de una referencia que no existe: {data.reference}'
            )

        return PaymentService.apply_gateway_status(
            payment,
            data.status,
            transaction_id=data.transaction_id,
            metadata=data.metadata,
            amount_in_cents=data.amount_in_cents,
            payment_method_type=data.payment_method_type,
        )

    @staticmethod
    def apply_gateway_status(payment, gateway_status, *, transaction_id='',
                             metadata=None, amount_in_cents=None,
                             payment_method_type='') -> Payment:
        """
        Traduce el estado de la pasarela y lo persiste de forma segura.

        Nunca se degrada un pago ya finalizado ni se toca el pedido en ese
        caso. Si el monto que reporta la pasarela no es el que guardamos, el
        estado se descarta: es la defensa que impide que un cobro alterado
        marque el pedido como pagado.
        """
        new_status = GATEWAY_STATUS_MAP.get(gateway_status.code)
        if new_status is None:
            raise InvalidStatusError(f'La pasarela devolvió un estado desconocido: {gateway_status.code}')

        with transaction.atomic():
            locked = Payment.objects.select_for_update().get(pk=payment.pk)

            if locked.is_final:
                logger.info(
                    'Evento repetido para el pago #%s: ya estaba en %s, se ignora.',
                    locked.pk, locked.status,
                )
                return locked

            if not _amount_agrees(locked, amount_in_cents):
                logger.error(
                    'El pago #%s referencia %s recibió un evento por %s centavos pero el pago es de %s. '
                    'No se aplica el estado.',
                    locked.pk, locked.reference, amount_in_cents, locked.amount,
                )
                return locked

            locked.status = new_status
            locked.status_message = gateway_status.message or ''
            if transaction_id and not locked.transaction_id:
                locked.transaction_id = transaction_id
            method = PAYMENT_METHOD_MAP.get((payment_method_type or '').upper())
            if method:
                locked.payment_method = method
            locked.metadata = {**(metadata or {})}
            if gateway_status.is_final:
                locked.mark_processed()
            locked.save(update_fields=[
                'status', 'status_message', 'transaction_id', 'payment_method',
                'metadata', 'processed_at', 'updated_at',
            ])

            if locked.is_successful:
                PaymentService._confirm_order(locked)

            return locked

    @staticmethod
    def update_status(payment, status) -> Payment:
        """Fuerza un estado desde el panel. No consulta la pasarela."""
        valid_statuses = [value for value, _ in Payment.Status.choices]
        if status not in valid_statuses:
            raise InvalidStatusError('El estado de pago no es válido.')

        with transaction.atomic():
            locked = Payment.objects.select_for_update().get(pk=payment.pk)
            # La comparación va contra la fila bloqueada, no contra el objeto que
            # pasó quien llama: si quedó desactualizado, se degradaría un pago
            # que en la base ya está cerrado.
            if locked.status == status:
                return locked
            if locked.is_final and status != Payment.Status.APROBADO:
                raise InvalidStatusError(
                    'Un pago finalizado no puede volver a un estado no aprobado.'
                )

            locked.status = status
            if locked.is_final:
                locked.mark_processed()
            locked.save(update_fields=['status', 'processed_at', 'updated_at'])
            if locked.is_successful:
                PaymentService._confirm_order(locked)
            return locked

    @staticmethod
    def _confirm_order(payment):
        """El pedido solo pasa a confirmado una vez, desde el estado pendiente."""
        order = payment.order
        if order.status != Order.Status.PENDIENTE:
            return

        order.status = Order.Status.CONFIRMADO
        order.save(update_fields=['status', 'updated_at'])
        OrderStatusHistory.objects.create(
            order=order,
            status=Order.Status.CONFIRMADO,
            comment=f'Pago aprobado por {payment.get_gateway_display()} (referencia {payment.reference}).',
        )


def _amount_agrees(payment, amount_in_cents):
    """
    Contrasta los centavos que informa la pasarela con el pago guardado.

    `None` significa que la fuente no trajo monto (por ejemplo una prueba), y en
    ese caso no hay nada que contradecir.
    """
    if amount_in_cents is None:
        return True
    return to_cents(payment.amount) == amount_in_cents