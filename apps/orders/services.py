import logging
from decimal import Decimal

from django.db import transaction

from apps.users.models import Address
from apps.cart.models import Cart, CartItem
from apps.orders.models import Order, OrderItem, OrderStatusHistory
from apps.inventory.services import (
    InventoryService,
    InsufficientStockError,
)
from apps.users.services import GmailService


logger = logging.getLogger(__name__)


class EmptyCartError(Exception):
    pass


class InvalidAddressError(Exception):
    pass


def checkout_cart(user, address_id: int, notes: str = '', site_url: str = '') -> Order:
    """
    Procesa el checkout transformando el carrito en un pedido final.

    La operación es completamente atómica:
    - Valida la dirección.
    - Valida el carrito.
    - Crea el pedido.
    - Descuenta el inventario.
    - Crea los items del pedido.
    - Calcula el total.
    - Vacía el carrito.
    - (on_commit) Envia un correo de confirmación utilizando GmailService.

    Si cualquier paso falla, toda la operación se revierte.
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
            raise EmptyCartError(
                'No se encontró el carrito.'
            )

        cart_items = list(
            CartItem.objects
            .filter(cart=cart)
            .select_related('product')
        )

        if not cart_items:
            raise EmptyCartError(
                'El carrito está vacío.'
            )

        # ─────────────────────────────────────────────
        # 3. Crear pedido
        # ─────────────────────────────────────────────

        order = Order.objects.create(
            user=user,
            status=Order.Status.PENDIENTE,
            shipping_address=address_snapshot,
            notes=notes.strip(),
            total=Decimal('0.00'),
        )

        OrderStatusHistory.objects.create(
            order=order,
            status=Order.Status.PENDIENTE,
            comment='Pedido realizado',
            changed_by=user,
        )
        # ─────────────────────────────────────────────
        # 4. Procesar productos
        # ─────────────────────────────────────────────

        total = Decimal('0.00')

        for cart_item in cart_items:

            product = cart_item.product
            quantity = cart_item.quantity

            # Guardamos el precio actual antes de cualquier
            # operación posterior sobre el producto.
            unit_price = product.price

            # Descontar inventario.
            # Si no hay suficiente stock, lanza
            # InsufficientStockError y se revierte todo.
            InventoryService.remove_stock(
                product=product,
                quantity=quantity,
                reason=f'Pedido #{order.id}',
                created_by=user,
            )

            # Crear item del pedido.
            OrderItem.objects.create(
                order=order,
                product=product,
                product_name=product.name,
                quantity=quantity,
                unit_price=unit_price,
            )

            total += unit_price * quantity

        # ─────────────────────────────────────────────
        # 5. Guardar total
        # ─────────────────────────────────────────────

        order.total = total
        order.save(update_fields=['total'])

        # ─────────────────────────────────────────────
        # 6. Vaciar carrito
        # ─────────────────────────────────────────────

        CartItem.objects.filter(cart=cart).delete()

        # ─────────────────────────────────────────────
        # 7. Programar envío de email de confirmación
        # ─────────────────────────────────────────────

        def send_confirmation():
            try:
                # Se recarga el pedido para asegurar que items y todo estén correctos
                # en el hilo de estado posterior al commit (aunque on_commit corre síncrono por defecto en runserver)
                order.refresh_from_db()
                context = {
                    'order': order,
                    'site_url': site_url if site_url else ''
                }
                GmailService.send_message(
                    subject=f'¡Tu pedido #{order.id} está confirmado!',
                    recipient=user.email,
                    text_template='orders/emails/order_confirmation.txt',
                    html_template='orders/emails/order_confirmation.html',
                    context=context,
                )
            except Exception as exc:
                # Capturar cualquier error para no afectar retroactivamente (on_commit igual no afecta la transaccion)
                logger.error(f'Error al enviar correo de confirmación para el pedido #{order.id}: {exc}')

        transaction.on_commit(send_confirmation)

        # ─────────────────────────────────────────────
        # 8. Devolver pedido
        # ─────────────────────────────────────────────

        return order