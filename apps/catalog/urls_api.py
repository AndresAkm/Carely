from django.urls import path, include
from rest_framework import routers

from .views.api import ProductViewSet, CategoryViewSet


router = routers.DefaultRouter()

router.register('productos', ProductViewSet, basename='productos')
router.register('categorias', CategoryViewSet, basename='categorias')

urlpatterns = [
    path('', include(router.urls)),
]