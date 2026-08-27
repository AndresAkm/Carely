from django.urls import path

from .views import web as views

app_name = 'cart'

urlpatterns = [
    path('', views.cart_view, name='cart'),
    path('agregar/<int:product_pk>/', views.cart_add, name='add'),
    path('actualizar/<int:product_pk>/', views.cart_update, name='update'),
    path('eliminar/<int:product_pk>/', views.cart_remove, name='remove'),
]
