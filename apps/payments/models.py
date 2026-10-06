import secrets

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


def build_reference() -> str:
    """
    Referencia única de la transacción en la pasarela.

    Wompi rechaza el reuse de una referencia, así que se genera al crear el pago
    y nunca se modifica. Solo admite alfanuméricos, guiones y guiones bajos.
    """
    return f'CARELY-{secrets.token_hex(10).upper()}'


class Payment(models.Model):
    class Gateway(models.TextChoices):
        WOMPI = 'wompi', 'Wompi'
        SIMULADO = 'simulado', 'Simulado'

    class PaymentMethod(models.TextChoices):
        CARD = 'card', 'Tarjeta de crédito'
        PSE = 'pse', 'PSE'
        NEQUI = 'nequi', 'Nequi'
        BANCOLOMBIA_TRANSFER = 'bancolombia_transfer', 'Transferencia Bancolombia'
        DAVIPLATA = 'daviplata', 'Daviplata'
        EFECTIVO = 'efectivo', 'Efectivo'

    class Status(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        APROBADO = 'aprobado', 'Aprobado'
        RECHAZADO = 'rechazado', 'Rechazado'
        ANULADO = 'anulado', 'Anulado'
        CANCELADO = 'cancelado', 'Cancelado'
        ERROR = 'error', 'Error'

    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.PROTECT,
        related_name='payments',
        verbose_name='pedido',
    )
    gateway = models.CharField(
        'pasarela',
        max_length=20,
        choices=Gateway.choices,
        default=Gateway.WOMPI,
    )
    reference = models.CharField(
        'referencia',
        max_length=255,
        unique=True,
        blank=True,
        editable=False,
        help_text='Referencia única de la transacción en la pasarela. Solo admite letras, dígitos, guiones y guiones bajos.',
    )
    transaction_id = models.CharField(
        'ID de transacción',
        max_length=255,
        null=True,
        blank=True,
        unique=True,
        help_text='Identificador que asigna la pasarela. Llenado cuando Wompi responde o notifica el evento.',
    )
    amount = models.DecimalField(
        'monto',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    payment_method = models.CharField(
        'método de pago',
        max_length=30,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CARD,
    )
    status = models.CharField(
        'estado',
        max_length=20,
        choices=Status.choices,
        default=Status.PENDIENTE,
    )
    status_message = models.CharField(
        'mensaje del estado',
        max_length=255,
        blank=True,
        help_text='Texto que devuelve la pasarela con el último estado recibido.',
    )
    metadata = models.JSONField(
        'metadatos',
        default=dict,
        blank=True,
        help_text='Datos no sensibles de la respuesta de la pasarela (tipo de método, IP, centavos cobrados).',
    )
    processed_at = models.DateTimeField(
        'procesado en',
        null=True,
        blank=True,
        help_text='Momento en que la transacción alcanzó un estado final.',
    )
    created_at = models.DateTimeField('creado', auto_now_add=True)
    updated_at = models.DateTimeField('actualizado', auto_now=True)

    class Meta:
        verbose_name = 'pago'
        verbose_name_plural = 'pagos'
        ordering = ['-created_at']

    def __str__(self):
        return f'Pago #{self.id} - Pedido #{self.order_id} - {self.get_status_display()}'

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = build_reference()
        super().save(*args, **kwargs)

    @property
    def is_successful(self):
        return self.status == self.Status.APROBADO

    @property
    def is_final(self):
        """Un estado final no se sobrescribe con otra notificación."""
        return self.status in {
            self.Status.APROBADO,
            self.Status.RECHAZADO,
            self.Status.ANULADO,
            self.Status.CANCELADO,
        }

    def mark_processed(self):
        self.processed_at = timezone.now()