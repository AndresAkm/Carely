from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models.deletion import ProtectedError
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from apps.core.permissions import is_admin

from ..forms import CategoryForm, ProductForm
from ..models import Category, Product


class DashboardAdminMixin(LoginRequiredMixin, UserPassesTestMixin):
    template_name_suffix = '_dashboard'

    def test_func(self):
        return is_admin(self.request.user)

    def handle_no_permission(self):
        return redirect('core:home')


class CategoryListView(DashboardAdminMixin, ListView):
    model = Category
    context_object_name = 'categories'
    template_name = 'catalog/dashboard/category_list.html'
    paginate_by = 8


class CategoryCreateView(DashboardAdminMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = 'catalog/dashboard/category_form.html'
    success_url = reverse_lazy('dashboard:category_list')

    def form_valid(self, form):
        messages.success(self.request, 'La categoría se creó correctamente.')
        return super().form_valid(form)


class CategoryUpdateView(DashboardAdminMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = 'catalog/dashboard/category_form.html'
    success_url = reverse_lazy('dashboard:category_list')

    def form_valid(self, form):
        messages.success(self.request, 'La categoría se actualizó correctamente.')
        return super().form_valid(form)


class CategoryDeleteView(DashboardAdminMixin, DeleteView):
    model = Category
    template_name = 'catalog/dashboard/category_confirm_delete.html'
    success_url = reverse_lazy('dashboard:category_list')

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
        except ProtectedError:
            messages.error(self.request, 'No puedes eliminar una categoría que todavía tiene productos.')
            return redirect(self.success_url)
        messages.success(self.request, 'La categoría se eliminó correctamente.')
        return response


class ProductListView(DashboardAdminMixin, ListView):
    model = Product
    context_object_name = 'products'
    template_name = 'catalog/dashboard/product_list.html'
    paginate_by = 8

    def get_queryset(self):
        return Product.objects.select_related('category')


class ProductCreateView(DashboardAdminMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = 'catalog/dashboard/product_form.html'
    success_url = reverse_lazy('dashboard:product_list')

    def form_valid(self, form):
        messages.success(self.request, 'El producto se creó correctamente.')
        return super().form_valid(form)


class ProductUpdateView(DashboardAdminMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = 'catalog/dashboard/product_form.html'
    success_url = reverse_lazy('dashboard:product_list')

    def form_valid(self, form):
        messages.success(self.request, 'El producto se actualizó correctamente.')
        return super().form_valid(form)


class ProductDeleteView(DashboardAdminMixin, DeleteView):
    model = Product
    template_name = 'catalog/dashboard/product_confirm_delete.html'
    success_url = reverse_lazy('dashboard:product_list')

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
        except ProtectedError:
            messages.error(self.request, 'No puedes eliminar un producto que está asociado a pedidos o movimientos de inventario.')
            return redirect(self.success_url)
        messages.success(self.request, 'El producto se eliminó correctamente.')
        return response
