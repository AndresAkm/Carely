from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
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


class CartItemViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOwnedOrAdmin]
    queryset = CartItem.objects.all()
    serializer_class = CartItemSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset if is_admin(self.request.user) else queryset.filter(cart__user=self.request.user)

    def perform_create(self, serializer):
        cart = serializer.validated_data['cart']
        if not is_admin(self.request.user) and cart.user_id != self.request.user.id:
            raise PermissionDenied('No puedes modificar el carrito de otro usuario.')
        serializer.save()
