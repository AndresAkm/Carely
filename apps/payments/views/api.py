from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import *
from ..serializer import *
from ..services import PaymentService
from apps.core.permissions import IsAuthenticatedOrAdminReadOnly, is_admin
from apps.orders.models import Order


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticatedOrAdminReadOnly]
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset if is_admin(self.request.user) else queryset.filter(order__user=self.request.user)

    @action(detail=False, methods=['post'], url_path='simular', url_name='simular', permission_classes=[IsAuthenticated])
    def simulate(self, request):
        """Registra y aprueba un pago simulado para un pedido pendiente.

        No habla con Wompi: crea el `Payment` con la pasarela `simulado` y usa
        el mismo servicio que confirma los pagos reales, para que el pedido y
        su historial queden igual que en un pago aprobado.
        """
        order_id = request.data.get('order_id')
        method = request.data.get('payment_method') or Payment.PaymentMethod.CARD
        valid_methods = [value for value, _ in Payment.PaymentMethod.choices]
        if method not in valid_methods:
            return Response({'detail': 'El método de pago no es válido.'}, status=400)

        try:
            order = Order.objects.get(pk=order_id, user=request.user)
        except (Order.DoesNotExist, ValueError, TypeError):
            return Response({'detail': 'El pedido no existe.'}, status=404)

        if order.status != Order.Status.PENDIENTE:
            return Response(
                {'detail': 'El pedido ya no está pendiente de pago.'},
                status=400,
            )
        if order.payments.filter(status=Payment.Status.APROBADO).exists():
            return Response({'detail': 'El pedido ya fue pagado.'}, status=400)
        if order.total <= 0:
            return Response(
                {'detail': 'El pedido no tiene un total válido para cobrar.'},
                status=400,
            )

        payment = order.payments.filter(status=Payment.Status.PENDIENTE).first()
        if payment is None:
            payment = Payment.objects.create(
                order=order,
                gateway=Payment.Gateway.SIMULADO,
                amount=order.total,
                payment_method=method,
                status=Payment.Status.PENDIENTE,
            )
        else:
            payment.gateway = Payment.Gateway.SIMULADO
            payment.payment_method = method
            payment.save(update_fields=['gateway', 'payment_method', 'updated_at'])

        payment = PaymentService.update_status(payment, Payment.Status.APROBADO)
        order.refresh_from_db()
        return Response(
            {
                'payment': PaymentSerializer(payment).data,
                'order_status': order.status,
                'estado_texto': order.get_status_display(),
            },
            status=201,
        )
