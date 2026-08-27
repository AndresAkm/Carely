import logging
from decimal import Decimal

from django.db import transaction

from apps.users.models import Address
from apps.cart.models import Cart, CartItem
from apps.orders.models import Coupon, Order, OrderItem, OrderStatusHistory
from apps.inventory.services import (
    InventoryService,
    InsufficientStockError,
)
from apps.users.services import GmailService


logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Excepciones de dominio
# ─────────────────────────────────────────────────────────────────────────────

class EmptyCartError(Exception):
    pass


class InvalidAddressError(Exception):
    pass


class InvalidCouponError(Exception):
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Servicio de cupones
# ─────────────────────────────────────────────────────────────────────────────

def get_coupon(code: str) -> Coupon:
    """
    Retorna el Coupon con el código dado (normalizado a mayúsculas).
    Lanza InvalidCouponError si no existe.
    """
    code = code.strip().upper()
    if not code:
        raise InvalidCouponError('El código del cupón está vacío.')
    try:
        return Coupon.objects.get(code=code)
    except Coupon.DoesNotExist:
        raise InvalidCouponError(f'El cupón "{code}" no existe.')


def validate_coupon(code: str, subtotal: Decimal) -> tuple[Coupon, Decimal]:
    """
    Valida un cupón y retorna (coupon, discount_amount).
    Lanza InvalidCouponError con mensaje descriptivo si es inválido.
    """
    coupon = get_coupon(code)
    valid, reason = coupon.is_valid(subtotal)
    if not valid:
        raise InvalidCouponError(reason)
    discount = coupon.calculate_discount(subtotal)
    return coupon, discount


# ─────────────────────────────────────────────────────────────────────────────
# Checkout
# ─────────────────────────────────────────────────────────────────────────────

def checkout_cart(
    user,
    address_id: int,
    notes: str = '',
    coupon_code: str = '',
    site_url: str = '',
) -> Order:
    """
    Procesa el checkout transformando el carrito en un pedido final.

    Operación completamente atómica:
      1. Valida la dirección.
      2. Valida el carrito.
      3. Valida el cupón (si se proporcionó) con select_for_update() para evitar
         condiciones de carrera en usage_limit.
      4. Crea el pedido.
      5. Descuenta el inventario.
      6. Crea los items del pedido.
      7. Calcula subtotal, aplica descuento y guarda total.
      8. Incrementa usage_count del cupón.
      9. Vacía el carrito.
      10. (on_commit) Envía correo de confirmación.

    Si cualquier paso falla, toda la operación se revierte.

    Política de cancelación de cupones:
      El usage_count se incrementa al crear el pedido. Cancelar posteriormente
      un pedido NO devuelve el uso del cupón automáticamente. Esta es una
      política deliberada para evitar abuso (colocar y cancelar pedidos para
      reciclar cupones de uso único).
    """

    with transaction.atomic():

        # ─────────────────────────────────────────────
        # 1. Validar dirección
        # ─────────────────────────────────────────────

        try:
            address = Address.objects.get(
                id=address_id,
                user=user,
                is_active=True,
            )
        except Address.DoesNotExist:
            raise InvalidAddressError(
                'La dirección seleccionada no es válida o no pertenece al usuario.'
            )

        address_snapshot = (
            f"{address.recipient_name}\n"
            f"{address.address_line}\n"
            f"{address.address_line2}\n"
            f"{address.city}, {address.department}\n"
            f"CP: {address.postal_code}\n"
            f"Tel: {address.phone}\n"
            f"Instrucciones: {address.instructions}"
        ).strip()

        # ─────────────────────────────────────────────
        # 2. Obtener carrito
        # ─────────────────────────────────────────────

        try:
            cart = Cart.objects.get(user=user)
        except Cart.DoesNotExist:
            raise EmptyCartError('No se encontró el carrito.')

        cart_items = list(
            CartItem.objects
            .filter(cart=cart)
            .select_related('product')
        )

        if not cart_items:
            raise EmptyCartError('El carrito está vacío.')

        # ─────────────────────────────────────────────
        # 3. Calcular subtotal (en backend, nunca desde frontend)
        # ─────────────────────────────────────────────

        subtotal = sum(
            (item.product.price * item.quantity for item in cart_items),
            Decimal('0.00'),
        )

        # ─────────────────────────────────────────────
        # 4. Validar y bloquear cupón (select_for_update evita race conditions)
        # ─────────────────────────────────────────────

        coupon_obj = None
        discount_amount = Decimal('0.00')
        coupon_code_snapshot = ''

        if coupon_code and coupon_code.strip():
            normalized_code = coupon_code.strip().upper()
            try:
                # select_for_update bloquea la fila hasta el commit.
                coupon_obj = Coupon.objects.select_for_update().get(code=normalized_code)
            except Coupon.DoesNotExist:
                raise InvalidCouponError(f'El cupón "{normalized_code}" no existe.')

            valid, reason = coupon_obj.is_valid(subtotal)
            if not valid:
                raise InvalidCouponError(reason)

            discount_amount = coupon_obj.calculate_discount(subtotal)
            coupon_code_snapshot = coupon_obj.code

        # ─────────────────────────────────────────────
        # 5. Crear pedido base
        # ─────────────────────────────────────────────

        order = Order(
            user=user,
            status=Order.Status.PENDIENTE,
            shipping_address=address_snapshot,
            notes=notes.strip(),
            total=Decimal('0.00'),
            coupon=coupon_obj,
            coupon_code=coupon_code_snapshot,
            discount_amount=discount_amount,
        )
        # Llamar a models.Model.save directamente para saltarse Order.save()
        # (que intenta recalcular total desde items, que todavía no existen).
        from django.db.models import Model as DjangoModel
        DjangoModel.save(order)

        OrderStatusHistory.objects.create(
            order=order,
            status=Order.Status.PENDIENTE,
            comment='Pedido realizado',
            changed_by=user,
        )

        # ─────────────────────────────────────────────
        # 6. Procesar productos (inventario + items)
        # ─────────────────────────────────────────────

        for cart_item in cart_items:
            product = cart_item.product
            quantity = cart_item.quantity
            unit_price = product.price

            InventoryService.remove_stock(
                product=product,
                quantity=quantity,
                reason=f'Pedido #{order.id}',
                created_by=user,
            )

            OrderItem.objects.create(
                order=order,
                product=product,
                product_name=product.name,
                quantity=quantity,
                unit_price=unit_price,
            )

        # ─────────────────────────────────────────────
        # 7. Calcular total final (subtotal - descuento)
        # ─────────────────────────────────────────────

        total = max(subtotal - discount_amount, Decimal('0.00'))
        order.total = total
        # Pasar 'total' en update_fields para que Order.save() no recalcule.
        Order.objects.filter(pk=order.pk).update(total=total)

        # ─────────────────────────────────────────────
        # 8. Incrementar usage_count del cupón
        # ─────────────────────────────────────────────

        if coupon_obj is not None:
            Coupon.objects.filter(pk=coupon_obj.pk).update(
                usage_count=coupon_obj.usage_count + 1
            )

        # ─────────────────────────────────────────────
        # 9. Vaciar carrito
        # ─────────────────────────────────────────────

        CartItem.objects.filter(cart=cart).delete()

        # ─────────────────────────────────────────────
        # 10. Programar envío de email de confirmación
        # ─────────────────────────────────────────────

        def send_confirmation():
            try:
                order.refresh_from_db()
                context = {
                    'order': order,
                    'site_url': site_url if site_url else '',
                }
                GmailService.send_message(
                    subject=f'¡Tu pedido #{order.id} está confirmado!',
                    recipient=user.email,
                    text_template='orders/emails/order_confirmation.txt',
                    html_template='orders/emails/order_confirmation.html',
                    context=context,
                )
            except Exception as exc:
                logger.error(
                    f'Error al enviar correo de confirmación para el pedido #{order.id}: {exc}'
                )

        transaction.on_commit(send_confirmation)

        return order