from rest_framework import viewsets
from ..models import *
from ..serializer import *
from apps.core.permissions import IsAuthenticatedOrAdminReadOnly, is_admin


class OrderViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOrAdminReadOnly]
    queryset = Order.objects.all()
    serializer_class = OrderSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset if is_admin(self.request.user) else queryset.filter(user=self.request.user)

    def get_permissions(self):
        if self.request.method in ('GET', 'HEAD', 'OPTIONS'):
            return [IsAuthenticatedOrAdminReadOnly()]
        from apps.core.permissions import IsAdminOnly
        return [IsAdminOnly()]


class OrderItemViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOrAdminReadOnly]
    queryset = OrderItem.objects.all()
    serializer_class = OrderItemSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset if is_admin(self.request.user) else queryset.filter(order__user=self.request.user)

    def get_permissions(self):
        if self.request.method in ('GET', 'HEAD', 'OPTIONS'):
            return [IsAuthenticatedOrAdminReadOnly()]
        from apps.core.permissions import IsAdminOnly
        return [IsAdminOnly()]
