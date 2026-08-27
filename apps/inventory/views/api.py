from rest_framework import viewsets
from ..models import *
from ..serializer import *
from apps.core.permissions import IsAdminOnly


class InventoryMovementViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOnly]
    queryset = InventoryMovement.objects.all()
    serializer_class = InventoryMovementSerializer
