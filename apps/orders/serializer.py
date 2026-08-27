from rest_framework import serializers

from .models import Order, OrderItem


class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = '__all__'
        read_only_fields = ['id', 'user', 'total', 'status', 'created_at', 'updated_at']


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = '__all__'
        read_only_fields = ['id', 'order', 'unit_price']

    def validate_product(self, product):
        if not product.is_active:
            raise serializers.ValidationError('No se pueden agregar productos inactivos a un pedido.')
        return product
