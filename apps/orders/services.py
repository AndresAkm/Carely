from decimal import Decimal
from django.db import transaction

from apps.users.models import Address
from apps.cart.models import Cart, CartItem
from apps.orders.models import Order, OrderItem
from apps.inventory.services import InventoryService, InsufficientStockError


class EmptyCartError(Exception):
    pass


class InvalidAddressError(Exception):
    pass


def checkout_cart(user, address_id: int, notes: str = '') -> Order:
    """
    Procesa el checkout transformando un carrito en un pedido final.
    Operación 100% atómica.
    """
    with transaction.atomic():
        # Validar dirección
        try:
            address = Address.objects.get(id=address_id, user=user, is_active=True)
        except Address.DoesNotExist:
            raise InvalidAddressError('La dirección seleccionada no es válida o no pertenece al usuario.')
            
        address_snapshot = (
            f"{address.recipient_name}\n"
            f"{address.address_line}\n"
            f"{address.address_line2}\n"
            f"{address.city}, {address.department}\n"
            f"CP: {address.postal_code}\n"
            f"Tel: {address.phone}\n"
            f"Instrucciones: {address.instructions}"
        ).strip()
        
        # Validar carrito
        try:
            cart = Cart.objects.get(user=user)
        except Cart.DoesNotExist:
            raise EmptyCartError('No se encontró el carrito.')
            
        # Select for update en los items para evitar condiciones de carrera si cambian por detrás
        # aunque InventoryService maneja el lock sobre Product
        cart_items = list(
            CartItem.objects.filter(cart=cart).select_related('product')
        )
        
        if not cart_items:
            raise EmptyCartError('El carrito está vacío.')
            
        # Crear orden
        order = Order.objects.create(
            user=user,
            status=Order.Status.PENDIENTE,
            shipping_address=address_snapshot,
            notes=notes,
            total=Decimal('0.00'),  # Se calculará al final o via signal
        )
        
        # Procesar items
        for citem in cart_items:
            product = citem.product
            qty = citem.quantity
            
            # Remover inventario (LANZA InsufficientStockError si no hay)
            InventoryService.remove_stock(
                product=product, 
                quantity=qty, 
                reason=f'Pedido #{order.id}', 
                created_by=user
            )
            
            OrderItem.objects.create(
                order=order,
                product=product,
                product_name=product.name,
                quantity=qty,
                unit_price=product.price
            )
            
        # Recalcular el total
        order.calculate_total()
        
        # Vaciar carrito
        CartItem.objects.filter(cart=cart).delete()
        
        return order
