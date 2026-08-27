from django.contrib import admin, messages
from django.utils.html import format_html

from .models import InventoryMovement
from .services import InsufficientStockError, InventoryService


@admin.register(InventoryMovement)
class InventoryMovementAdmin(admin.ModelAdmin):
    """
    Admin de SOLO LECTURA para el historial de movimientos.

    Los movimientos se crean a través de las acciones definidas en
    ProductAdmin (ver `entrada_stock`, `salida_stock`, `ajuste_stock`).
    Esto garantiza que la creación de movimientos siempre pase por
    InventoryService y que Product.stock se mantenga consistente.
    """

    list_display = ['product', 'colored_quantity', 'movement_type', 'reason', 'created_by', 'created_at']
    list_filter = ['movement_type', 'created_at']
    search_fields = ['product__name', 'reason', 'created_by__email']
    readonly_fields = [
        'product', 'quantity', 'movement_type',
        'reason', 'created_by', 'created_at', 'updated_at',
    ]

    def has_add_permission(self, request):
        """Los movimientos no se crean directamente: se usan las acciones en ProductAdmin."""
        return False

    def has_change_permission(self, request, obj=None):
        """El historial es inmutable."""
        return False

    def has_delete_permission(self, request, obj=None):
        """El historial no se borra."""
        return False

    @admin.display(description='cantidad')
    def colored_quantity(self, obj):
        color = {
            InventoryMovement.MovementType.ENTRADA: '#2ecc71',
            InventoryMovement.MovementType.SALIDA: '#e74c3c',
            InventoryMovement.MovementType.AJUSTE: '#f39c12',
        }.get(obj.movement_type, '#555')
        sign = '+' if obj.movement_type == InventoryMovement.MovementType.ENTRADA else (
            '-' if obj.movement_type == InventoryMovement.MovementType.SALIDA else ('±' if obj.quantity >= 0 else '')
        )
        return format_html(
            '<strong style="color:{}">{}{}</strong>',
            color,
            sign if obj.movement_type != InventoryMovement.MovementType.AJUSTE else ('+' if obj.quantity >= 0 else ''),
            obj.quantity,
        )


class InventoryInline(admin.TabularInline):
    """
    Inline de historial de movimientos en ProductAdmin.
    De solo lectura — las operaciones se hacen con los botones de acción.
    """
    model = InventoryMovement
    extra = 0
    fields = ['movement_type', 'quantity', 'reason', 'created_by', 'created_at']
    readonly_fields = ['movement_type', 'quantity', 'reason', 'created_by', 'created_at']
    ordering = ['-created_at']
    max_num = 0  # no permitir añadir movimientos desde el inline

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
