from django.urls import path

from apps.catalog.views.dashboard import (
    CategoryCreateView,
    CategoryDeleteView,
    CategoryListView,
    CategoryUpdateView,
    ProductCreateView,
    ProductDeleteView,
    ProductListView,
    ProductUpdateView,
)
from apps.core.report_views import ReportExportView, ReportView
from apps.orders.views.dashboard import OrderDetailView, OrderListView, OrderStatusUpdateView
from apps.users.views.dashboard import UserCreateView, UserForceDeleteView, UserListView, UserPasswordChangeView, UserToggleActiveView, UserUpdateView

app_name = 'dashboard'

urlpatterns = [
    path('pedidos/', OrderListView.as_view(), name='order_list'),
    path('pedidos/<int:pk>/', OrderDetailView.as_view(), name='order_detail'),
    path('pedidos/<int:pk>/estado/', OrderStatusUpdateView.as_view(), name='order_status'),
    path('reportes/', ReportView.as_view(), name='report_list'),
    path('reportes/exportar/', ReportExportView.as_view(), name='report_export'),
    path('productos/', ProductListView.as_view(), name='product_list'),
    path('productos/nuevo/', ProductCreateView.as_view(), name='product_create'),
    path('productos/<int:pk>/editar/', ProductUpdateView.as_view(), name='product_update'),
    path('productos/<int:pk>/eliminar/', ProductDeleteView.as_view(), name='product_delete'),
    path('categorias/', CategoryListView.as_view(), name='category_list'),
    path('categorias/nueva/', CategoryCreateView.as_view(), name='category_create'),
    path('categorias/<int:pk>/editar/', CategoryUpdateView.as_view(), name='category_update'),
    path('categorias/<int:pk>/eliminar/', CategoryDeleteView.as_view(), name='category_delete'),
    path('usuarios/', UserListView.as_view(), name='user_list'),
    path('usuarios/nuevo/', UserCreateView.as_view(), name='user_create'),
    path('usuarios/forzar-eliminacion/', UserForceDeleteView.as_view(), name='user_force_delete'),
    path('usuarios/<int:pk>/editar/', UserUpdateView.as_view(), name='user_update'),
    path('usuarios/<int:pk>/password/', UserPasswordChangeView.as_view(), name='user_password'),
    path('usuarios/<int:pk>/estado/', UserToggleActiveView.as_view(), name='user_toggle_active'),
]
