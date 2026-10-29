from rest_framework import serializers

from apps.core.permissions import is_admin

from .models import *


class CartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_price = serializers.SerializerMethodField()
    product_image = serializers.SerializerMethodField()
    stock = serializers.IntegerField(source='product.stock', read_only=True)
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = '__all__'
        read_only_fields = ['id']
        # El alta de un producto que ya está en el carrito se resuelve sumando
        # cantidades en el viewset; el validador automático de `unique_together`
        # lo rechazaría antes de llegar ahí.
        validators = []

    def get_product_price(self, obj):
        return f'{obj.product.price:.2f}'

    def get_product_image(self, obj):
        if not obj.product.image:
            return None
        url = obj.product.image.url
        request = self.context.get('request')
        return request.build_absolute_uri(url) if request else url

    def get_subtotal(self, obj):
        return f'{obj.subtotal:.2f}'

    def validate_cart(self, cart):
        user = self.context['request'].user
        if not is_admin(user) and cart.user_id != user.id:
            raise serializers.ValidationError(
                'No puedes modificar el carrito de otro usuario.',
            )
        return cart

    def validate_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError('La cantidad debe ser al menos 1.')
        return value

    def validate(self, attrs):
        product = attrs.get('product') or getattr(self.instance, 'product', None)
        quantity = attrs.get('quantity', getattr(self.instance, 'quantity', None))
        if product is not None and quantity is not None and quantity > product.stock:
            raise serializers.ValidationError({
                'quantity': f'Solo hay {product.stock} unidades disponibles.',
            })

        cart = attrs.get('cart') or getattr(self.instance, 'cart', None)
        if self.instance is not None and cart is not None and product is not None:
            duplicado = CartItem.objects.filter(
                cart=cart, product=product,
            ).exclude(pk=self.instance.pk)
            if duplicado.exists():
                raise serializers.ValidationError({
                    'product': 'Ese producto ya está en el carrito.',
                })
        return attrs


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ['id', 'user', 'items', 'total', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

    def get_total(self, obj):
        return f'{obj.total:.2f}'
