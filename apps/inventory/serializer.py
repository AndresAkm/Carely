from rest_framework import serializers

from apps.catalog.models import Product

from .models import InventoryMovement


class InventoryMovementSerializer(serializers.ModelSerializer):
    """
    Serializer de solo lectura para el historial de movimientos.

    Expone campos explícitos (no __all__) y añade el nombre del
    producto y del usuario como campos calculados de conveniencia.
    """
    product_name = serializers.CharField(source='product.name', read_only=True)
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True, default=None)

    class Meta:
        model = InventoryMovement
        fields = [
            'id',
            'product',
            'product_name',
            'quantity',
            'movement_type',
            'reason',
            'created_by',
            'created_by_email',
            'created_at',
        ]
        read_only_fields = fields  # el historial es inmutable desde la API


class StockEntrySerializer(serializers.Serializer):
    """Datos necesarios para registrar una ENTRADA de stock."""
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError('La cantidad debe ser mayor que cero.')
        return value


class StockRemoveSerializer(serializers.Serializer):
    """Datos necesarios para registrar una SALIDA de stock."""
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')

    def validate(self, data):
        product = data['product']
        quantity = data['quantity']
        if product.stock < quantity:
            raise serializers.ValidationError(
                f'Stock insuficiente. Disponible: {product.stock}, solicitado: {quantity}.'
            )
        return data


class StockAdjustSerializer(serializers.Serializer):
    """Datos necesarios para realizar un AJUSTE de stock."""
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    new_stock = serializers.IntegerField(min_value=0)
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
