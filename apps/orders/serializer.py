from rest_framework import serializers

from .models import Order, OrderItem, OrderStatusHistory


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = '__all__'
        read_only_fields = ['id', 'order', 'unit_price']

    def validate_product(self, product):
        if not product.is_active:
            raise serializers.ValidationError('No se pueden agregar productos inactivos a un pedido.')
        return product


class OrderItemReadSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            'id', 'product', 'product_name', 'quantity', 'unit_price',
            'subtotal', 'image',
        ]

    def get_image(self, obj):
        if not obj.product.image:
            return None
        url = obj.product.image.url
        request = self.context.get('request')
        return request.build_absolute_uri(url) if request else url

    def get_subtotal(self, obj):
        return str(obj.subtotal)


class OrderStatusHistorySerializer(serializers.ModelSerializer):
    estado_texto = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = OrderStatusHistory
        fields = ['id', 'status', 'estado_texto', 'comment', 'created_at']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemReadSerializer(many=True, read_only=True)
    status_history = OrderStatusHistorySerializer(many=True, read_only=True)
    estado_texto = serializers.CharField(source='get_status_display', read_only=True)
    payment = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = '__all__'
        read_only_fields = [
            'id', 'user', 'total', 'status', 'channel', 'created_at', 'updated_at',
        ]

    def get_payment(self, obj):
        payment = obj.payments.order_by('-created_at').first()
        if payment is None:
            return None
        return {
            'id': payment.id,
            'reference': payment.reference,
            'gateway': payment.gateway,
            'amount': str(payment.amount),
            'payment_method': payment.payment_method,
            'status': payment.status,
            'estado_texto': payment.get_status_display(),
        }
