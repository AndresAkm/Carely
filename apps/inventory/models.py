from django.db import models
from django.conf import settings


class InventoryMovement(models.Model):
    class MovementType(models.TextChoices):
        ENTRADA = 'entrada', 'Entrada'
        SALIDA = 'salida', 'Salida'
        AJUSTE = 'ajuste', 'Ajuste'

    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.PROTECT,
        related_name='inventory_movements',
        verbose_name='producto',
    )
    quantity = models.IntegerField('cantidad')
    movement_type = models.CharField(
        'tipo de movimiento',
        max_length=20,
        choices=MovementType.choices,
    )
    reason = models.CharField('motivo', max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inventory_movements',
        verbose_name='creado por',
    )
    created_at = models.DateTimeField('creado', auto_now_add=True)
    updated_at = models.DateTimeField('actualizado', auto_now=True)

    class Meta:
        verbose_name = 'movimiento de inventario'
        verbose_name_plural = 'movimientos de inventario'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_movement_type_display()} - {self.product.name} ({self.quantity})'
