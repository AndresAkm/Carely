from django.urls import path, include
from rest_framework import routers
from .views.api import InventoryMovementViewSet


router = routers.DefaultRouter()
router.register('movimientos', InventoryMovementViewSet, basename='movimientos')

urlpatterns = [
    path('', include(router.urls)),
]
