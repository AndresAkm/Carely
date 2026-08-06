from django.urls import path, include
from rest_framework import routers
from .views.api import OrderViewSet, OrderItemViewSet


router = routers.DefaultRouter()
router.register('pedidos', OrderViewSet, basename='pedidos')
router.register('items-pedido', OrderItemViewSet, basename='items-pedido')

urlpatterns = [
    path('', include(router.urls)),
]
