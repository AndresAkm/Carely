from django.urls import include, path
from rest_framework import routers

from apps.catalog.views.api import CategoryViewSet, ProductViewSet
from apps.users.views.api import AddressViewSet, UserViewSet
from apps.inventory.views.api import InventoryMovementViewSet
from apps.cart.views.api import CartItemViewSet, CartViewSet
from apps.orders.views.api import OrderItemViewSet, OrderViewSet
from apps.payments.views.api import PaymentViewSet

router = routers.DefaultRouter()

router.register('catalogo/productos', ProductViewSet, basename='productos')
router.register('catalogo/categorias', CategoryViewSet, basename='categorias')
router.register('usuarios', UserViewSet, basename='usuarios')
router.register('direcciones', AddressViewSet, basename='direcciones')
router.register('inventario/movimientos', InventoryMovementViewSet, basename='movimientos')
router.register('carrito/carritos', CartViewSet, basename='carritos')
router.register('carrito/items', CartItemViewSet, basename='items-carrito')
router.register('pedidos/pedidos', OrderViewSet, basename='pedidos')
router.register('pedidos/items', OrderItemViewSet, basename='items-pedido')
router.register('pagos', PaymentViewSet, basename='pagos')

urlpatterns = [
    path('', include(router.urls)),
]
