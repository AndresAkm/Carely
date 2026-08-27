"""
cart/services.py
================
Lógica de negocio para el carrito de compras.

REGLAS:
- El carrito se crea automáticamente para el usuario si no existe.
- La cantidad de un item no puede superar Product.stock.
- Si quantity llega a 0, el item se elimina del carrito.
- No se modifica Product.stock aquí (eso ocurre solo en el checkout).
"""
from __future__ import annotations

from django.db import transaction

from apps.catalog.models import Product

from .models import Cart, CartItem


class CartStockError(Exception):
    """Se lanza cuando la cantidad solicitada supera el stock disponible."""


def get_or_create_cart(user) -> Cart:
    """Obtiene o crea el carrito para el usuario autenticado."""
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


@transaction.atomic
def add_item(user, product: Product, quantity: int = 1) -> CartItem:
    """
    Agrega `quantity` unidades de `product` al carrito del usuario.

    Si el producto ya existe en el carrito, suma la cantidad.
    Valida que la cantidad total no supere Product.stock.

    Raises:
        CartStockError: Si quantity total > product.stock.
        ValueError:     Si quantity <= 0.
    """
    if quantity <= 0:
        raise ValueError('La cantidad debe ser mayor que cero.')

    cart = get_or_create_cart(user)
    item, created = CartItem.objects.select_for_update().get_or_create(
        cart=cart,
        product=product,
        defaults={'quantity': 0},
    )
    new_quantity = item.quantity + quantity
    if new_quantity > product.stock:
        raise CartStockError(
            f'Solo hay {product.stock} unidades disponibles de "{product.name}". '
            f'Ya tienes {item.quantity} en tu carrito.'
        )
    item.quantity = new_quantity
    item.save(update_fields=['quantity'])
    return item


@transaction.atomic
def update_item_quantity(user, product: Product, quantity: int) -> CartItem | None:
    """
    Establece la cantidad exacta de `product` en el carrito.

    Si quantity <= 0 o > stock: elimina o lanza error.
    Retorna None si el item fue eliminado.

    Raises:
        CartStockError: Si quantity > product.stock.
    """
    try:
        item = CartItem.objects.select_for_update().get(cart__user=user, product=product)
    except CartItem.DoesNotExist:
        return None

    if quantity <= 0:
        item.delete()
        return None

    if quantity > product.stock:
        raise CartStockError(
            f'Solo hay {product.stock} unidades disponibles de "{product.name}".'
        )
    item.quantity = quantity
    item.save(update_fields=['quantity'])
    return item


@transaction.atomic
def remove_item(user, product: Product) -> bool:
    """
    Elimina completamente el item del carrito.
    Retorna True si existía, False si no.
    """
    deleted, _ = CartItem.objects.filter(cart__user=user, product=product).delete()
    return deleted > 0


def get_cart_context(user) -> dict:
    """
    Devuelve un dict con toda la información del carrito para los templates.
    """
    cart = get_or_create_cart(user)
    items = cart.items.select_related('product', 'product__category').all()
    return {
        'cart': cart,
        'cart_items': items,
        'cart_total': cart.total,
        'cart_count': sum(i.quantity for i in items),
    }
