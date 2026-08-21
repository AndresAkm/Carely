from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import PasswordChangeView
from django.db import transaction
from django.shortcuts import redirect
from django.views import View
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from apps.core.permissions import is_admin
from apps.payments.models import Payment

from ..forms import DashboardUserCreateForm, DashboardUserForm, ForceDeleteUserForm
from ..models import User


class DashboardUserMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return is_admin(self.request.user)

    def handle_no_permission(self):
        return redirect('core:home')


class UserListView(DashboardUserMixin, ListView):
    model = User
    template_name = 'users/dashboard/user_list.html'
    context_object_name = 'users'
    paginate_by = 8

    def get_queryset(self):
        queryset = User.objects.all()
        search = self.request.GET.get('q', '').strip()
        role = self.request.GET.get('role', '')
        status = self.request.GET.get('status', '')
        if search:
            queryset = queryset.filter(first_name__icontains=search) | queryset.filter(last_name__icontains=search) | queryset.filter(email__icontains=search)
        if role in User.Role.values:
            queryset = queryset.filter(role=role)
        if status == 'active':
            queryset = queryset.filter(is_active=True)
        elif status == 'inactive':
            queryset = queryset.filter(is_active=False)
        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['force_delete_form'] = ForceDeleteUserForm()
        return context


class UserCreateView(DashboardUserMixin, CreateView):
    model = User
    form_class = DashboardUserCreateForm
    template_name = 'users/dashboard/user_form.html'
    success_url = reverse_lazy('dashboard:user_list')

    def form_valid(self, form):
        messages.success(self.request, 'El usuario se creó correctamente.')
        return super().form_valid(form)


class UserUpdateView(DashboardUserMixin, UpdateView):
    model = User
    form_class = DashboardUserForm
    template_name = 'users/dashboard/user_form.html'
    success_url = reverse_lazy('dashboard:user_list')

    def form_valid(self, form):
        if self.object == self.request.user and not form.cleaned_data['is_active']:
            form.add_error('is_active', 'No puedes desactivar tu propia cuenta.')
            return self.form_invalid(form)
        if (
            self.object.role == User.Role.ADMIN
            and self.object.is_active
            and (form.cleaned_data['role'] != User.Role.ADMIN or not form.cleaned_data['is_active'])
            and User.objects.filter(is_active=True, role=User.Role.ADMIN).count() <= 1
        ):
            form.add_error('role', 'No puedes quitar los permisos del último administrador activo.')
            return self.form_invalid(form)
        messages.success(self.request, 'El usuario se actualizó correctamente.')
        return super().form_valid(form)


class UserPasswordChangeView(DashboardUserMixin, PasswordChangeView):
    template_name = 'users/dashboard/user_password.html'
    success_url = reverse_lazy('dashboard:user_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.get_object()
        return kwargs

    def get_object(self):
        return User.objects.get(pk=self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['object'] = self.get_object()
        return context

    def form_valid(self, form):
        messages.success(self.request, 'La contraseña se actualizó correctamente.')
        return super().form_valid(form)


class UserToggleActiveView(DashboardUserMixin, UpdateView):
    model = User
    fields = []
    success_url = reverse_lazy('dashboard:user_list')

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object == request.user:
            messages.error(request, 'No puedes desactivar tu propia cuenta.')
        elif self.object.is_active and self.object.role == User.Role.ADMIN and User.objects.filter(is_active=True, role=User.Role.ADMIN).count() <= 1:
            messages.error(request, 'No puedes desactivar al último administrador activo.')
        else:
            self.object.is_active = not self.object.is_active
            self.object.save(update_fields=['is_active', 'updated_at'])
            action = 'activó' if self.object.is_active else 'desactivó'
            messages.success(request, f'Se {action} el usuario correctamente.')
        return redirect(self.success_url)


class UserForceDeleteView(DashboardUserMixin, View):
    def post(self, request, *args, **kwargs):
        form = ForceDeleteUserForm(request.POST)
        if not form.is_valid():
            messages.error(request, 'Selecciona un usuario válido para eliminar.')
            return redirect('dashboard:user_list')

        user = form.get_target_user()
        if user == request.user:
            messages.error(request, 'No puedes eliminar la cuenta con la que estás usando el dashboard.')
            return redirect('dashboard:user_list')
        if (
            user.role == User.Role.ADMIN
            and user.is_active
            and User.objects.filter(is_active=True, role=User.Role.ADMIN).count() <= 1
        ):
            messages.error(request, 'No puedes eliminar al último administrador activo.')
            return redirect('dashboard:user_list')

        with transaction.atomic():
            # Payments protect their order, so remove the payment records first.
            Payment.objects.filter(order__user=user).delete()
            user.delete()
        messages.success(request, 'El usuario y sus datos relacionados se eliminaron correctamente.')
        return redirect('dashboard:user_list')
