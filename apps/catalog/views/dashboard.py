from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from apps.core.permissions import is_admin

from ..forms import CategoryForm, ProductFilterForm, ProductForm
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
        queryset = Product.objects.select_related('category').order_by('-created_at')
        self.filter_form = ProductFilterForm(self.request.GET or None)
        if not self.filter_form.is_valid():
            return queryset

        filters = self.filter_form.cleaned_data
        search = filters.get('q')
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(description__icontains=search))
        if filters.get('category'):
            queryset = queryset.filter(category=filters['category'])
        if filters.get('is_active'):
            queryset = queryset.filter(is_active=filters['is_active'] == 'True')
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = getattr(self, 'filter_form', ProductFilterForm(self.request.GET or None))
        query = self.request.GET.copy()
        query.pop('page', None)
        context['filter_query'] = query.urlencode()
        return context



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
