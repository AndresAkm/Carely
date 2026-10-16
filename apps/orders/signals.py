from decimal import Decimal

from django.conf import settings
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import Order, OrderItem
from .services import notify_order_status_update


def recalculate_order_total(order_id):
    order = Order.objects.filter(pk=order_id).first()
    if order is None:
        return
    subtotal = sum(
        (unit_price * quantity for unit_price, quantity in OrderItem.objects.filter(
            order_id=order_id,
        ).values_list('unit_price', 'quantity')),
        Decimal('0.00'),
    )
    total = max(subtotal - order.discount_amount, Decimal('0.00'))
    Order.objects.filter(pk=order_id).update(total=total)


@receiver(post_save, sender=OrderItem)
def update_total_after_item_save(sender, instance, **kwargs):
    recalculate_order_total(instance.order_id)


@receiver(post_delete, sender=OrderItem)
def update_total_after_item_delete(sender, instance, **kwargs):
    recalculate_order_total(instance.order_id)


@receiver(pre_save, sender=Order)
def capture_previous_order_status(sender, instance, **kwargs):
    """Guarda el estado previo antes de que el `save` lo pise.

    El formulario de Django ya mutó `instance.status` antes de llegar aquí
    (construct_instance), así que el valor "viejo" solo se puede leer de la
    base de datos.
    """
    if instance.pk:
        instance._previous_status = (
            Order.objects.filter(pk=instance.pk)
            .values_list('status', flat=True)
            .first()
        )


@receiver(post_save, sender=Order)
def notify_order_status_changed(sender, instance, **kwargs):
    """Avisa al cliente cuando el estado del pedido cambia a uno relevante.

    Cubre todos los caminos que mueven el estado (dashboard, admin de Django y
    API). `notify_order_status_update` solo envía correo para ENVIADO, ENTREGADO
    y CANCELADO, así que el resto de cambios no genera nada.
    """
    previous = getattr(instance, '_previous_status', None)
    if previous is None or previous == instance.status:
        return
    notify_order_status_update(instance, site_url=settings.SITE_URL)
