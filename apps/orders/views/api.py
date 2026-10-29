from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import *
from ..serializer import *
from ..services import EmptyCartError, InvalidAddressError, InvalidCouponError, checkout_cart
from apps.inventory.services import InsufficientStockError
from apps.core.permissions import IsAuthenticatedOrAdminReadOnly, is_admin


class OrderViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOrAdminReadOnly]
    queryset = Order.objects.all()
    serializer_class = OrderSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset if is_admin(self.request.user) else queryset.filter(user=self.request.user)

    def get_permissions(self):
        if self.action == 'checkout':
            return [IsAuthenticated()]
        if self.request.method in ('GET', 'HEAD', 'OPTIONS'):
            return [IsAuthenticatedOrAdminReadOnly()]
        from apps.core.permissions import IsAdminOnly
        return [IsAdminOnly()]

    @action(detail=False, methods=['post'], url_path='checkout')
    def checkout(self, request):
        """Convierte el carrito del usuario en un pedido."""
        address_id = request.data.get('address_id')
        notes = request.data.get('notes', '')
        if not address_id:
            return Response(
                {'detail': 'Debes seleccionar una dirección de envío.'},
                status=400,
            )
        try:
            address_id = int(address_id)
        except (TypeError, ValueError):
            return Response(
                {'detail': 'La dirección de envío no es válida.'},
                status=400,
            )

        try:
            order = checkout_cart(
                request.user,
                address_id,
                notes=notes,
                site_url=request.build_absolute_uri('/')[:-1],
            )
        except (EmptyCartError, InvalidAddressError, InvalidCouponError, InsufficientStockError) as exc:
            return Response({'detail': str(exc)}, status=400)

        return Response(
            OrderSerializer(order, context=self.get_serializer_context()).data,
            status=201,
        )


class OrderItemViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOrAdminReadOnly]
    queryset = OrderItem.objects.all()
    serializer_class = OrderItemSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if not is_admin(self.request.user):
            queryset = queryset.filter(order__user=self.request.user)
        order_id = self.request.query_params.get('order')
        if order_id:
            queryset = queryset.filter(order_id=order_id)
        return queryset

    def get_permissions(self):
        if self.request.method in ('GET', 'HEAD', 'OPTIONS'):
            return [IsAuthenticatedOrAdminReadOnly()]
        from apps.core.permissions import IsAdminOnly
        return [IsAdminOnly()]
