from django.urls import path, include
from rest_framework import routers

from .views.api import UserViewSet


router = routers.DefaultRouter()

router.register('usuarios', UserViewSet, basename='usuarios')

urlpatterns = [
    path('', include(router.urls)),
]
