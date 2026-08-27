from django.urls import path
from .views import web as views

app_name = 'orders'

urlpatterns = [
    path('checkout/', views.checkout_view, name='checkout'),
    path('exito/<int:order_id>/', views.order_success_view, name='success'),
    path('', views.order_list_view, name='order_list'),
    path('<int:order_id>/', views.order_detail_view, name='order_detail'),
]
