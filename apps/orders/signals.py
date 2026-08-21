from decimal import Decimal

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Order, OrderItem


def recalculate_order_total(order_id):
    total = sum(
        (unit_price * quantity for unit_price, quantity in OrderItem.objects.filter(
            order_id=order_id,
        ).values_list('unit_price', 'quantity')),
        Decimal('0.00'),
    )
    Order.objects.filter(pk=order_id).update(total=total)


@receiver(post_save, sender=OrderItem)
def update_total_after_item_save(sender, instance, **kwargs):
    recalculate_order_total(instance.order_id)


@receiver(post_delete, sender=OrderItem)
def update_total_after_item_delete(sender, instance, **kwargs):
    recalculate_order_total(instance.order_id)
