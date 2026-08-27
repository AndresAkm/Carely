from django.urls import path
from .views import web as views

app_name = 'orders'

urlpatterns = [
    path('checkout/', views.checkout_view, name='checkout'),
    path('exito/<int:order_id>/', views.order_success_view, name='success'),
    path('cupones/validar/', views.validate_coupon_ajax, name='validate_coupon_ajax'),
    path('', views.order_list_view, name='order_list'),
    path('<int:order_id>/', views.order_detail_view, name='order_detail'),
]
