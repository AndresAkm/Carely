from rest_framework import viewsets
from ..models import *
from ..serializer import *
from apps.core.permissions import IsAdminOrReadOnly


class InventoryMovementViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    queryset = InventoryMovement.objects.all()
    serializer_class = InventoryMovementSerializer
