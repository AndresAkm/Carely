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
from apps.users.views.dashboard import UserCreateView, UserListView, UserPasswordChangeView, UserToggleActiveView, UserUpdateView

app_name = 'dashboard'

urlpatterns = [
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
    path('usuarios/<int:pk>/editar/', UserUpdateView.as_view(), name='user_update'),
    path('usuarios/<int:pk>/password/', UserPasswordChangeView.as_view(), name='user_password'),
    path('usuarios/<int:pk>/estado/', UserToggleActiveView.as_view(), name='user_toggle_active'),
]
