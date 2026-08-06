from django.urls import path, include
from rest_framework import routers
from .views.api import PaymentViewSet


router = routers.DefaultRouter()
router.register('pagos', PaymentViewSet, basename='pagos')

urlpatterns = [
    path('', include(router.urls)),
]
