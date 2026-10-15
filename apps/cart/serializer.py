from rest_framework import serializers

from apps.core.permissions import is_admin

from .models import *


class CartSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cart
        fields = '__all__'
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']


class CartItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CartItem
        fields = '__all__'
        read_only_fields = ['id']

    def validate_cart(self, cart):
        user = self.context['request'].user
        if not is_admin(user) and cart.user_id != user.id:
            raise serializers.ValidationError(
                'No puedes modificar el carrito de otro usuario.',
            )
        return cart
