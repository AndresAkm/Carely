from rest_framework import viewsets
from ..models import *
from ..serializer import *
from apps.core.permissions import IsAdminOrReadOnly


class CartViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    queryset = Cart.objects.all()
    serializer_class = CartSerializer


class CartItemViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    queryset = CartItem.objects.all()
    serializer_class = CartItemSerializer
