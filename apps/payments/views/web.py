import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.orders.models import Order
from apps.payments.gateways import GatewayError
from apps.payments.models import Payment
from apps.payments.services import (
    InvalidEventError,
    PaymentAlreadyExistsError,
    PaymentError,
    PaymentNotFoundError,
    PaymentService,
    find_active_payment,
)


logger = logging.getLogger(__name__)

#: Header con el que Wompi manda el checksum del evento.
CHECKSUM_HEADER = 'HTTP_X_EVENT_CHECKSUM'


@login_required
@require_POST
def payment_start_view(request, order_id):
    """
    Prepara el pago de un pedido y manda al cliente al checkout de la pasarela.

    Es idempotente desde el lado del usuario: si el pedido ya tiene un pago en
    curso se reutiliza en vez de crear otro.
    """
    order = get_object_or_404(Order, id=order_id, user=request.user)

    try:
        payment = find_active_payment(order)
        if payment is None:
            payment = PaymentService.create_payment(order)
        checkout_url = PaymentService.start_checkout(payment, request)
    except PaymentAlreadyExistsError:
        return redirect('orders:success', order_id=order.id)
    except (GatewayError, PaymentError) as error:
        logger.error('No se pudo iniciar el pago del pedido #%s: %s', order.id, error)
        messages.error(request, str(error))
        return redirect('orders:success', order_id=order.id)

    return redirect(checkout_url)


@login_required
@require_GET
def payment_return_view(request, payment_id):
    """
    Pantalla a la que Wompi devuelve al cliente tras intentar el pago.

    Wompi llega aquí con `?id=<transaccion>`; ese identificador solo se usa para
    preguntar a la pasarela. El estado que se muestra es el que responde Wompi
    desde el backend, nunca el de la URL.
    """
    payment = get_object_or_404(Payment, id=payment_id, order__user=request.user)

    transaction_id = request.GET.get('id', '').strip()
    if transaction_id and not payment.transaction_id:
        payment.transaction_id = transaction_id
        payment.save(update_fields=['transaction_id', 'updated_at'])

    if payment.transaction_id and not payment.is_final:
        try:
            payment = PaymentService.sync_with_gateway(payment)
        except (GatewayError, PaymentError) as error:
            logger.warning('No se pudo verificar el pago #%s: %s', payment.id, error)
            messages.warning(request, str(error))

    return render(request, 'payments/return.html', {'payment': payment})


@login_required
@require_GET
def payment_status_view(request, payment_id):
    """Estado del pago en JSON. Nunca devuelve llaves ni datos de la pasarela."""
    payment = get_object_or_404(Payment, id=payment_id, order__user=request.user)

    if request.GET.get('consultar') and payment.transaction_id and not payment.is_final:
        try:
            payment = PaymentService.sync_with_gateway(payment)
        except (GatewayError, PaymentError) as error:
            logger.warning('No se pudo verificar el pago #%s: %s', payment.id, error)
            return JsonResponse({'error': str(error)}, status=503)

    return JsonResponse({
        'id': payment.id,
        'estado': payment.status,
        'estado_texto': payment.get_status_display(),
        'monto': str(payment.amount),
        'es_pagado': payment.is_successful,
        'es_final': payment.is_final,
    })


@csrf_exempt
@require_http_methods(['POST'])
def wompi_webhook_view(request):
    """
    Recibe `transaction.updated` de Wompi y refleja el estado en el pago.

    Wompi reintenta hasta 3 veces mientras no reciba un 200, así que se
    contesta 200 también cuando el evento no es nuestro o ya se había
    aplicado. Solo un 400 (cuerpo ilegible o firma inválida) dispara reintentos.
    """
    try:
        payload = json.loads(request.body or b'{}')
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.error('Webhook de Wompi con cuerpo ilegible.')
        return JsonResponse({'detail': 'Cuerpo ilegible.'}, status=400)

    if not isinstance(payload, dict):
        return JsonResponse({'detail': 'Cuerpo ilegible.'}, status=400)

    try:
        payment = PaymentService.handle_event(
            payload,
            checksum=request.META.get(CHECKSUM_HEADER, ''),
        )
    except InvalidEventError:
        logger.error('Webhook de Wompi con firma inválida.')
        return JsonResponse({'detail': 'Firma inválida.'}, status=400)
    except PaymentNotFoundError as error:
        logger.warning('Webhook de Wompi: %s', error)
        return JsonResponse({'detail': 'Referencia desconocida.'}, status=200)
    except (GatewayError, PaymentError, ValueError) as error:
        logger.error('Webhook de Wompi no se pudo procesar: %s', error)
        return JsonResponse({'detail': 'Evento no procesado.'}, status=200)

    return JsonResponse({'estado': payment.status}, status=200)


# ─────────────────────────────────────────────────────────────────────────────
# Checkout simulado (PAYMENT_GATEWAY=simulado)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_GET
def simulated_checkout_view(request, reference):
    """
    Pantalla que imita al checkout alojado para poder probar el flujo entero
    sin sandbox. Solo existe cuando `PAYMENT_GATEWAY=simulado`.
    """
    payment = get_object_or_404(Payment, reference=reference, order__user=request.user)
    if payment.is_final:
        return redirect('payments:return_page', payment_id=payment.id)
    return render(request, 'payments/simulated.html', {'payment': payment})


@login_required
@require_POST
def simulated_result_view(request, reference):
    """Emite un evento con la misma forma que el de Wompi y lo pasa al servicio."""
    payment = get_object_or_404(Payment, reference=reference, order__user=request.user)
    if payment.is_final:
        return redirect('payments:return_page', payment_id=payment.id)

    status = 'APPROVED' if request.POST.get('resultado') == 'aprobado' else 'DECLINED'
    payload = {
        'event': 'transaction.updated',
        'data': {
            'transaction': {
                'id': f'sim-{payment.reference}',
                'reference': payment.reference,
                'status': status,
                'amount_in_cents': int(payment.amount * 100),
                'currency': 'COP',
                'payment_method_type': 'SIMULATED',
                'status_message': 'Resultado simulado.',
            },
        },
    }

    try:
        PaymentService.handle_event(payload)
    except (GatewayError, PaymentError) as error:
        logger.warning('El checkout simulado no pudo resolverse: %s', error)
        messages.error(request, str(error))

    return redirect('payments:return_page', payment_id=payment.id)