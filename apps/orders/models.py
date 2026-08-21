from decimal import Decimal

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator


class Order(models.Model):
    class Status(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        CONFIRMADO = 'confirmado', 'Confirmado'
        ENVIADO = 'enviado', 'Enviado'
        ENTREGADO = 'entregado', 'Entregado'
        CANCELADO = 'cancelado', 'Cancelado'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orders',
        verbose_name='usuario',
    )
    status = models.CharField(
        'estado',
        max_length=20,
        choices=Status.choices,
        default=Status.PENDIENTE,
    )
    total = models.DecimalField('total', max_digits=12, decimal_places=2, default=0)
    shipping_address = models.TextField('dirección de envío', blank=True)
    notes = models.TextField('notas', blank=True)
    created_at = models.DateTimeField('creado', auto_now_add=True)
    updated_at = models.DateTimeField('actualizado', auto_now=True)

    class Meta:
        verbose_name = 'pedido'
        verbose_name_plural = 'pedidos'
        ordering = ['-created_at']

    def __str__(self):
        return f'Pedido #{self.id} - {self.user.email}'

    def save(self, *args, **kwargs):
        if self.pk:
            self.total = sum(
                (item.subtotal for item in self.items.all()),
                Decimal('0.00'),
            )
            if kwargs.get('update_fields') is not None:
                kwargs['update_fields'] = set(kwargs['update_fields']) | {'total'}
        else:
            self.total = Decimal('0.00')
        super().save(*args, **kwargs)

    def calculate_total(self):
        self.save(update_fields=['total'])


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='pedido',
    )
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.PROTECT,
        related_name='order_items',
        verbose_name='producto',
    )
    quantity = models.PositiveIntegerField(
        'cantidad',
        default=1,
        validators=[MinValueValidator(1)],
    )
    unit_price = models.DecimalField(
        'precio unitario',
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )

    class Meta:
        verbose_name = 'item de pedido'
        verbose_name_plural = 'items de pedido'
        ordering = ['-id']

    def __str__(self):
        return f'{self.product.name} x{self.quantity}'

    @property
    def subtotal(self):
        return self.unit_price * self.quantity
