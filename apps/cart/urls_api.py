from django.urls import path, include
from rest_framework import routers
from .views.api import CartViewSet, CartItemViewSet


router = routers.DefaultRouter()
router.register('carritos', CartViewSet, basename='carritos')
router.register('items-carrito', CartItemViewSet, basename='items-carrito')

urlpatterns = [
    path('', include(router.urls)),
]
