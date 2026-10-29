from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from ..models import *
from ..serializer import *
from apps.core.permissions import IsAuthenticatedOwnedOrAdmin, is_admin


class CartViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOwnedOrAdmin]
    queryset = Cart.objects.all()
    serializer_class = CartSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset if is_admin(self.request.user) else queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'], url_path='actual', url_name='actual')
    def current(self, request):
        """Devuelve el carrito del usuario, creándolo si todavía no existe."""
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return Response(self.get_serializer(cart).data)


class CartItemViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOwnedOrAdmin]
    queryset = CartItem.objects.all()
    serializer_class = CartItemSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset if is_admin(self.request.user) else queryset.filter(cart__user=self.request.user)

    def perform_create(self, serializer):
        """Suma la cantidad si el producto ya está en el carrito."""
        data = serializer.validated_data
        cart = data['cart']
        product = data['product']
        quantity = data.get('quantity', 1)
        item = CartItem.objects.filter(cart=cart, product=product).first()
        if item is None:
            serializer.save()
            return

        total_quantity = item.quantity + quantity
        if total_quantity > product.stock:
            raise serializers.ValidationError({
                'quantity': f'Solo hay {product.stock} unidades disponibles.',
            })
        item.quantity = total_quantity
        item.save(update_fields=['quantity'])
        serializer.instance = item
