from rest_framework import viewsets
from ..models import *
from ..serializer import *
from apps.core.permissions import IsAuthenticatedOrAdminReadOnly, is_admin


class PaymentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOrAdminReadOnly]
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset if is_admin(self.request.user) else queryset.filter(order__user=self.request.user)
