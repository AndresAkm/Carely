from django.db import models


class Payment(models.Model):
    class PaymentMethod(models.TextChoices):
        TARJETA = 'tarjeta', 'Tarjeta'
        TRANSFERENCIA = 'transferencia', 'Transferencia'
        EFECTIVO = 'efectivo', 'Efectivo'

    class Status(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        COMPLETADO = 'completado', 'Completado'
        FALLIDO = 'fallido', 'Fallido'
        REEMBOLSADO = 'reembolsado', 'Reembolsado'

    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name='pedido',
    )
    amount = models.DecimalField('monto', max_digits=12, decimal_places=2)
    payment_method = models.CharField(
        'método de pago',
        max_length=20,
        choices=PaymentMethod.choices,
    )
    status = models.CharField(
        'estado',
        max_length=20,
        choices=Status.choices,
        default=Status.PENDIENTE,
    )
    transaction_id = models.CharField(
        'ID de transacción',
        max_length=255,
        blank=True,
    )
    created_at = models.DateTimeField('creado', auto_now_add=True)
    updated_at = models.DateTimeField('actualizado', auto_now=True)

    class Meta:
        verbose_name = 'pago'
        verbose_name_plural = 'pagos'
        ordering = ['-created_at']

    def __str__(self):
        return f'Pago #{self.id} - Pedido #{self.order.id} - {self.get_status_display()}'
