import json
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.cart.services import get_cart_context
from apps.orders.models import Order
from apps.orders.services import (
    EmptyCartError,
    InvalidAddressError,
    InvalidCouponError,
    checkout_cart,
    validate_coupon,
)
from apps.inventory.services import InsufficientStockError
from apps.users.models import Address


# ─────────────────────────────────────────────────────────────────────────────
# Checkout
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def checkout_view(request):
    """
    Vista para el checkout web.
    Permite seleccionar una dirección activa, aplicar un cupón y confirmar el pedido.

    POST con action='apply_coupon': Valida el cupón y almacena el código en sesión.
    POST con action='confirm'     : Confirma el pedido (revalida todo en backend).
    """
    context = get_cart_context(request.user)

    if not context.get('cart_items'):
        messages.warning(
            request,
            'Tu carrito está vacío. Agrega productos para poder proceder al pago.'
        )
        return redirect('cart:cart')

    addresses = Address.objects.select_related('city__department').filter(
        user=request.user, is_active=True
    ).order_by('-is_default', '-created_at')

    if request.method == 'POST':
        action = request.POST.get('action', 'confirm')

        # ── Aplicar cupón (preview) ──────────────────
        if action == 'apply_coupon':
            return _handle_apply_coupon(request, context, addresses)

        # ── Confirmar pedido ─────────────────────────
        if action == 'confirm':
            return _handle_confirm(request, context, addresses)

    # GET: limpiar cupón solo si el usuario lo solicita explícitamente
    if request.GET.get('clear_coupon'):
        request.session.pop('applied_coupon_code', None)
        return redirect('orders:checkout')

    # Mostrar cupón de sesión en contexto
    context.update(_coupon_context(request, context['cart_total']))
    context['addresses'] = addresses
    return render(request, 'orders/checkout.html', context)


def _handle_apply_coupon(request, context, addresses):
    """Valida el cupón y lo guarda en sesión. Redirige de vuelta al checkout."""
    coupon_code = request.POST.get('coupon_code', '').strip().upper()

    if not coupon_code:
        request.session.pop('applied_coupon_code', None)
        messages.warning(request, 'Introduce un código de cupón.')
        return redirect('orders:checkout')

    cart_total = context['cart_total']

    try:
        _, discount = validate_coupon(coupon_code, cart_total)
        request.session['applied_coupon_code'] = coupon_code
        messages.success(
            request,
            f'✓ Cupón {coupon_code} aplicado. Descuento: COP {discount:,.2f}'
        )
    except InvalidCouponError as e:
        request.session.pop('applied_coupon_code', None)
        messages.error(request, str(e))

    return redirect('orders:checkout')


def _handle_confirm(request, context, addresses):
    """Procesa el POST de confirmación de pedido."""
    address_id = request.POST.get('address_id')
    notes = request.POST.get('notes', '').strip()
    coupon_code = request.session.get('applied_coupon_code', '').strip()

    if not address_id:
        messages.error(request, 'Debes seleccionar una dirección de envío.')
        context.update(_coupon_context(request, context['cart_total']))
        context['addresses'] = addresses
        return render(request, 'orders/checkout.html', context)

    try:
        address_id = int(address_id)
        site_url = request.build_absolute_uri('/')[:-1]

        order = checkout_cart(
            request.user,
            address_id,
            notes=notes,
            coupon_code=coupon_code,
            site_url=site_url,
        )

        # Limpiar cupón de sesión al crear el pedido exitosamente.
        request.session.pop('applied_coupon_code', None)

        messages.success(
            request,
            f'¡Pedido #{order.id} confirmado con éxito!'
        )
        return redirect('orders:success', order_id=order.id)

    except InvalidAddressError as e:
        messages.error(request, str(e))

    except InvalidCouponError as e:
        # El cupón dejó de ser válido entre "Aplicar" y "Confirmar".
        request.session.pop('applied_coupon_code', None)
        messages.error(
            request,
            f'El cupón ya no es válido y el pedido no pudo procesarse: {e}'
        )

    except InsufficientStockError as e:
        messages.error(request, f'No pudimos procesar el pedido. {e}')
        return redirect('cart:cart')

    except EmptyCartError as e:
        messages.error(request, str(e))
        return redirect('cart:cart')

    except ValueError:
        messages.error(request, 'Selecciona una dirección de envío válida.')

    except Exception:
        messages.error(request, 'Ocurrió un error inesperado al procesar el pedido.')

    context.update(_coupon_context(request, context['cart_total']))
    context['addresses'] = addresses
    return render(request, 'orders/checkout.html', context)


def _coupon_context(request, cart_total: Decimal) -> dict:
    """Construye el contexto del cupón (código de sesión + preview del descuento)."""
    code = request.session.get('applied_coupon_code', '')
    if not code:
        return {'applied_coupon_code': '', 'coupon_discount': Decimal('0.00'), 'cart_total_with_discount': cart_total}

    try:
        from apps.orders.services import validate_coupon
        _, discount = validate_coupon(code, cart_total)
        total_with_discount = max(cart_total - discount, Decimal('0.00'))
        return {
            'applied_coupon_code': code,
            'coupon_discount': discount,
            'cart_total_with_discount': total_with_discount,
        }
    except InvalidCouponError:
        # El cupón expiró entre visitas — limpiar sesión.
        request.session.pop('applied_coupon_code', None)
        return {
            'applied_coupon_code': '',
            'coupon_discount': Decimal('0.00'),
            'cart_total_with_discount': cart_total,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint AJAX para validación rápida de cupón (opcional, para UX)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_POST
def validate_coupon_ajax(request):
    """
    Endpoint AJAX para validar un cupón en tiempo real.
    Retorna JSON con el resultado para actualizar el UI sin recargar.
    NUNCA es fuente de verdad para el checkout; solo es UX.
    """
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'valid': False, 'error': 'Petición inválida.'}, status=400)

    code = data.get('coupon_code', '').strip()
    cart_total_raw = data.get('cart_total')

    if not code:
        return JsonResponse({'valid': False, 'error': 'Introduce un código de cupón.'})

    try:
        cart_total = Decimal(str(cart_total_raw))
    except Exception:
        return JsonResponse({'valid': False, 'error': 'Total inválido.'}, status=400)

    try:
        coupon, discount = validate_coupon(code, cart_total)
        return JsonResponse({
            'valid': True,
            'code': coupon.code,
            'discount_type': coupon.discount_type,
            'discount_value': str(coupon.discount_value),
            'discount_amount': str(discount),
            'total_with_discount': str(max(cart_total - discount, Decimal('0.00'))),
        })
    except InvalidCouponError as e:
        return JsonResponse({'valid': False, 'error': str(e)})


# ─────────────────────────────────────────────────────────────────────────────
# Otras vistas existentes
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def order_success_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'orders/success.html', {'order': order})


@login_required
def order_list_view(request):
    """Lista todos los pedidos propios del usuario autenticado."""
    orders = Order.objects.filter(
        user=request.user
    ).order_by('-created_at').prefetch_related('items')
    return render(request, 'orders/order_list.html', {'orders': orders})


@login_required
def order_detail_view(request, order_id):
    """Ver un pedido en detalle por ID (aislado por user)."""
    order = get_object_or_404(
        Order.objects.select_related('user').prefetch_related(
            'items__product', 'items__product__category', 'status_history'
        ),
        id=order_id,
        user=request.user,
    )
    return render(request, 'orders/order_detail.html', {'order': order})
