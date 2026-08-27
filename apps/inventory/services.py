"""
inventory/services.py
=====================
Servicio centralizado para todas las operaciones de inventario.

ARQUITECTURA:
    ADMIN / CHECKOUT
           │
           ▼
    InventoryService
           │
           ├── modifica Product.stock  (fuente de verdad)
           └── crea InventoryMovement  (historial/auditoría)

CONVENCIÓN DE `quantity` EN InventoryMovement:
    - Siempre almacenada como valor POSITIVO.
    - El `movement_type` determina la semántica:
        · entrada  → cantidad ingresada al stock
        · salida   → cantidad retirada del stock
        · ajuste   → valor absoluto de la variación (puede ser + o -)
    - Para ajustes, la columna `quantity` almacena la variación neta
      (positiva si subió, negativa si bajó). Esto permite reconstruir
      el historial correctamente.

CONCURRENCIA:
    Cada operación de escritura emite un SELECT ... FOR UPDATE sobre el
    Product, garantizando que dos transacciones simultáneas no puedan
    decrementar el stock por debajo de cero.
"""

from __future__ import annotations

from django.db import transaction

from apps.catalog.models import Product

from .models import InventoryMovement


class InsufficientStockError(Exception):
    """Se lanza cuando el stock disponible es menor que la cantidad solicitada."""


class InventoryService:
    """
    Punto de entrada único para modificaciones de stock.

    Todas las operaciones son atómicas: o completan el par
    (Product.stock + InventoryMovement) o hacen rollback completo.
    """

    # ------------------------------------------------------------------
    # Operaciones públicas
    # ------------------------------------------------------------------

    @staticmethod
    def add_stock(
        product: Product,
        quantity: int,
        reason: str = '',
        created_by=None,
    ) -> InventoryMovement:
        """
        Incrementa Product.stock en `quantity` unidades.

        Args:
            product:    Instancia de Product (o pk — se recarga con lock).
            quantity:   Cantidad a añadir (debe ser > 0).
            reason:     Motivo textual del movimiento.
            created_by: Usuario responsable (User o None).

        Returns:
            El InventoryMovement creado.

        Raises:
            ValueError: Si quantity <= 0.
        """
        if quantity <= 0:
            raise ValueError(f'La cantidad de entrada debe ser positiva. Recibido: {quantity}')

        with transaction.atomic():
            locked = _lock_product(product)
            locked.stock += quantity
            locked.save(update_fields=['stock'])

            movement = InventoryMovement.objects.create(
                product=locked,
                quantity=quantity,
                movement_type=InventoryMovement.MovementType.ENTRADA,
                reason=reason,
                created_by=created_by,
            )

        return movement

    @staticmethod
    def remove_stock(
        product: Product,
        quantity: int,
        reason: str = '',
        created_by=None,
    ) -> InventoryMovement:
        """
        Decrementa Product.stock en `quantity` unidades.

        Args:
            product:    Instancia de Product.
            quantity:   Cantidad a retirar (debe ser > 0).
            reason:     Motivo textual del movimiento.
            created_by: Usuario responsable (User o None).

        Returns:
            El InventoryMovement creado.

        Raises:
            ValueError:             Si quantity <= 0.
            InsufficientStockError: Si Product.stock < quantity.
        """
        if quantity <= 0:
            raise ValueError(f'La cantidad de salida debe ser positiva. Recibido: {quantity}')

        with transaction.atomic():
            locked = _lock_product(product)

            if locked.stock < quantity:
                raise InsufficientStockError(
                    f'Stock insuficiente para "{locked.name}". '
                    f'Disponible: {locked.stock}, solicitado: {quantity}.'
                )

            locked.stock -= quantity
            locked.save(update_fields=['stock'])

            movement = InventoryMovement.objects.create(
                product=locked,
                quantity=quantity,
                movement_type=InventoryMovement.MovementType.SALIDA,
                reason=reason,
                created_by=created_by,
            )

        return movement

    @staticmethod
    def adjust_stock(
        product: Product,
        new_stock: int,
        reason: str = '',
        created_by=None,
    ) -> InventoryMovement:
        """
        Establece Product.stock al valor absoluto `new_stock`.

        La variación neta (new_stock - stock_anterior) se registra en
        InventoryMovement.quantity para permitir reconstruir el historial.
        Un ajuste positivo significa que el stock subió; negativo, que bajó.

        Args:
            product:    Instancia de Product.
            new_stock:  Nuevo valor absoluto de stock (debe ser >= 0).
            reason:     Motivo textual del ajuste.
            created_by: Usuario responsable (User o None).

        Returns:
            El InventoryMovement creado.

        Raises:
            ValueError: Si new_stock < 0.
        """
        if new_stock < 0:
            raise ValueError(f'El stock no puede ser negativo. Recibido: {new_stock}')

        with transaction.atomic():
            locked = _lock_product(product)
            variation = new_stock - locked.stock   # puede ser + o -

            locked.stock = new_stock
            locked.save(update_fields=['stock'])

            movement = InventoryMovement.objects.create(
                product=locked,
                quantity=variation,          # convención: variación neta
                movement_type=InventoryMovement.MovementType.AJUSTE,
                reason=reason,
                created_by=created_by,
            )

        return movement


# ------------------------------------------------------------------
# Helpers internos
# ------------------------------------------------------------------

def _lock_product(product: Product) -> Product:
    """
    Emite SELECT ... FOR UPDATE sobre el Product para serializar
    el acceso concurrente al stock.

    Acepta tanto una instancia como un pk entero.
    Debe ejecutarse dentro de un bloque transaction.atomic().
    """
    pk = product.pk if isinstance(product, Product) else product
    return Product.objects.select_for_update().get(pk=pk)
