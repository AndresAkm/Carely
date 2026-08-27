from decimal import Decimal

from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.conf import settings
from django.utils import timezone


# ─────────────────────────────────────────────────────────────────────────────
# COUPON
# ─────────────────────────────────────────────────────────────────────────────

class Coupon(models.Model):
    class DiscountType(models.TextChoices):
        PERCENTAGE = 'percentage', 'Porcentaje (%)'
        FIXED = 'fixed', 'Valor fijo (COP)'

    code = models.CharField(
        'código',
        max_length=50,
        unique=True,
        help_text='Código en mayúsculas. Ej: CARELY10',
    )
    discount_type = models.CharField(
        'tipo de descuento',
        max_length=10,
        choices=DiscountType.choices,
        default=DiscountType.PERCENTAGE,
    )
    discount_value = models.DecimalField(
        'valor del descuento',
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Porcentaje (ej: 10 = 10%) o valor fijo en COP (ej: 5000)',
    )
    is_active = models.BooleanField('activo', default=True)
    valid_from = models.DateTimeField('válido desde', null=True, blank=True)
    valid_until = models.DateTimeField('válido hasta', null=True, blank=True)
    usage_limit = models.PositiveIntegerField(
        'límite de usos',
        null=True,
        blank=True,
        help_text='Dejar vacío para usos ilimitados.',
    )
    usage_count = models.PositiveIntegerField('usos realizados', default=0)
    minimum_purchase = models.DecimalField(
        'mínimo de compra',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text='Subtotal mínimo requerido para usar este cupón.',
    )
    created_at = models.DateTimeField('creado', auto_now_add=True)
    updated_at = models.DateTimeField('actualizado', auto_now=True)

    class Meta:
        verbose_name = 'cupón'
        verbose_name_plural = 'cupones'
        ordering = ['-created_at']

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        # Normalizar código a mayúsculas siempre.
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def is_valid(self, subtotal: Decimal) -> tuple[bool, str]:
        """
        Retorna (True, '') si el cupón es válido para el subtotal dado.
        Retorna (False, mensaje) con la razón de rechazo.
        """
        if not self.is_active:
            return False, 'El cupón no está activo.'

        now = timezone.now()
        if self.valid_from and now < self.valid_from:
            return False, 'El cupón todavía no ha comenzado su vigencia.'
        if self.valid_until and now > self.valid_until:
            return False, 'El cupón ha expirado.'

        if self.usage_limit is not None and self.usage_count >= self.usage_limit:
            return False, 'El cupón ha alcanzado su límite de usos.'

        if subtotal < self.minimum_purchase:
            return False, (
                f'El subtotal mínimo para usar este cupón es '
                f'COP {self.minimum_purchase:,.2f}.'
            )

        # Validar el valor en sí
        if self.discount_type == self.DiscountType.PERCENTAGE:
            if self.discount_value <= 0 or self.discount_value > 100:
                return False, 'El porcentaje del cupón es inválido.'
        else:
            if self.discount_value <= 0:
                return False, 'El valor del descuento es inválido.'

        return True, ''

    def calculate_discount(self, subtotal: Decimal) -> Decimal:
        """
        Calcula el monto de descuento a aplicar.
        Nunca retorna un valor mayor al subtotal (no totales negativos).
        """
        if self.discount_type == self.DiscountType.PERCENTAGE:
            discount = (subtotal * self.discount_value / Decimal('100')).quantize(Decimal('0.01'))
        else:
            discount = self.discount_value

        # El descuento nunca puede superar el subtotal.
        return min(discount, subtotal)


# ─────────────────────────────────────────────────────────────────────────────
# ORDER
# ─────────────────────────────────────────────────────────────────────────────

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

    # ── Cupón / descuento ─────────────────────────────────
    # FK nullable con SET_NULL para conservar historial aunque el cupón se elimine.
    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
        verbose_name='cupón',
    )
    # Snapshot del código al momento de la compra (historial inmutable).
    coupon_code = models.CharField(
        'código de cupón',
        max_length=50,
        blank=True,
        default='',
    )
    # Monto real de descuento aplicado (snapshot).
    discount_amount = models.DecimalField(
        'descuento aplicado',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
    )

    created_at = models.DateTimeField('creado', auto_now_add=True)
    updated_at = models.DateTimeField('actualizado', auto_now=True)

    class Meta:
        verbose_name = 'pedido'
        verbose_name_plural = 'pedidos'
        ordering = ['-created_at']

    def __str__(self):
        return f'Pedido #{self.id} - {self.user.email}'

    def save(self, *args, **kwargs):
        """
        Recalcula el total SOLO si no se está usando update_fields explícito
        para el total (el servicio de checkout gestiona el total manualmente).
        Si se pasan update_fields y 'total' está entre ellos, Django usa el
        valor ya asignado en self.total sin recalcular.
        """
        update_fields = kwargs.get('update_fields')
        if update_fields is not None and 'total' in update_fields:
            # El llamador ya asignó self.total; respetar sin recalcular.
            super().save(*args, **kwargs)
            return

        if self.pk:
            subtotal = sum(
                (item.subtotal for item in self.items.all()),
                Decimal('0.00'),
            )
            self.total = max(subtotal - self.discount_amount, Decimal('0.00'))
        else:
            self.total = Decimal('0.00')
        super().save(*args, **kwargs)

    def calculate_total(self):
        self.save(update_fields=None)

    @property
    def subtotal(self) -> Decimal:
        """Suma bruta de items (sin descuento)."""
        return sum((item.subtotal for item in self.items.all()), Decimal('0.00'))


# ─────────────────────────────────────────────────────────────────────────────
# ORDER ITEM
# ─────────────────────────────────────────────────────────────────────────────

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
    product_name = models.CharField(
        'nombre del producto',
        max_length=200,
        default='',
        help_text='Snapshot del nombre del producto al momento de la compra',
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


# ─────────────────────────────────────────────────────────────────────────────
# ORDER STATUS HISTORY
# ─────────────────────────────────────────────────────────────────────────────

class OrderStatusHistory(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='status_history',
        verbose_name='pedido',
    )
    status = models.CharField(
        'estado',
        max_length=20,
        choices=Order.Status.choices,
    )
    comment = models.TextField('comentario', blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_status_changes',
        verbose_name='modificado por',
    )
    created_at = models.DateTimeField('fecha', auto_now_add=True)

    class Meta:
        verbose_name = 'historial de estado'
        verbose_name_plural = 'historial de estados'
        ordering = ['created_at']

    def __str__(self):
        return f'Pedido #{self.order.id} - {self.get_status_display()}'