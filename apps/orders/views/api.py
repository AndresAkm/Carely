from rest_framework import viewsets
from ..models import *
from ..serializer import *
from apps.core.permissions import IsAdminOrReadOnly


class OrderViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    queryset = Order.objects.all()
    serializer_class = OrderSerializer


class OrderItemViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    queryset = OrderItem.objects.all()
    serializer_class = OrderItemSerializer
