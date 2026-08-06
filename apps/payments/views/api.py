from rest_framework import viewsets
from ..models import *
from ..serializer import *
from apps.core.permissions import IsAdminOrReadOnly


class PaymentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
