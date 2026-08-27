from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import IsAdminOnly

from ..models import InventoryMovement
from ..serializer import (
    InventoryMovementSerializer,
    StockAdjustSerializer,
    StockEntrySerializer,
    StockRemoveSerializer,
)
from ..services import InsufficientStockError, InventoryService


class InventoryMovementViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Historial de movimientos de inventario (solo lectura).

    Solo los administradores pueden acceder. Las operaciones de escritura
    se realizan a través de las acciones custom:

        POST /api/v1/inventario/movimientos/entrada/
        POST /api/v1/inventario/movimientos/salida/
        POST /api/v1/inventario/movimientos/ajuste/

    Estas acciones delegan en InventoryService, que garantiza atomicidad
    y protección contra condiciones de carrera.
    """

    permission_classes = [IsAdminOnly]
    queryset = InventoryMovement.objects.select_related('product', 'created_by').all()
    serializer_class = InventoryMovementSerializer

    # ------------------------------------------------------------------
    # Acciones de escritura — delegan en InventoryService
    # ------------------------------------------------------------------

    @action(detail=False, methods=['post'], url_path='entrada')
    def entrada(self, request):
        """Registra una entrada de stock (aumenta Product.stock)."""
        serializer = StockEntrySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        movement = InventoryService.add_stock(
            product=data['product'],
            quantity=data['quantity'],
            reason=data.get('reason', ''),
            created_by=request.user,
        )
        return Response(
            InventoryMovementSerializer(movement).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['post'], url_path='salida')
    def salida(self, request):
        """Registra una salida de stock (reduce Product.stock)."""
        serializer = StockRemoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            movement = InventoryService.remove_stock(
                product=data['product'],
                quantity=data['quantity'],
                reason=data.get('reason', ''),
                created_by=request.user,
            )
        except InsufficientStockError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            InventoryMovementSerializer(movement).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['post'], url_path='ajuste')
    def ajuste(self, request):
        """Ajusta el stock absoluto de un producto."""
        serializer = StockAdjustSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        movement = InventoryService.adjust_stock(
            product=data['product'],
            new_stock=data['new_stock'],
            reason=data.get('reason', ''),
            created_by=request.user,
        )
        return Response(
            InventoryMovementSerializer(movement).data,
            status=status.HTTP_201_CREATED,
        )
