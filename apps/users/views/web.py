from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.views.generic import UpdateView
from django.views.generic import TemplateView

from apps.core.permissions import is_admin

from ..forms import LoginForm, ProfileForm, RegisterForm
from ..models import User
from ..services import GmailService, GmailServiceError


def get_redirect_url(user):
    if user.is_staff or user.is_superuser:
        return 'core:dashboard'
    return 'catalog:home'


class LoginView(View):
    template_name = 'users/login.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect(get_redirect_url(request.user))
        form = LoginForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            user = authenticate(request, username=email, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'¡Bienvenida de nuevo, {user.first_name}!')
                return redirect(get_redirect_url(user))
            else:
                messages.error(request, 'Correo electrónico o contraseña incorrectos.')
        return render(request, self.template_name, {'form': form})


class RegisterView(View):
    template_name = 'users/register.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect(get_redirect_url(request.user))
        form = RegisterForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            try:
                email_sent = GmailService.send_registration_confirmation(user, request)
            except GmailServiceError:
                email_sent = False
            login(request, user)
            request.session['registration_email'] = user.email
            request.session['registration_email_sent'] = email_sent
            return redirect('users:registration_confirmation')
        return render(request, self.template_name, {'form': form})


class LogoutView(View):
    def get(self, request):
        logout(request)
        messages.success(request, 'Has cerrado sesión correctamente.')
        return redirect('core:home')


class RegistrationConfirmationView(TemplateView):
    template_name = 'users/registration_confirmation.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['registration_email'] = self.request.session.pop('registration_email', '')
        context['registration_email_sent'] = self.request.session.pop('registration_email_sent', False)
        return context


class ProfileView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = ProfileForm
    template_name = 'users/profile.html'
    context_object_name = 'profile_user'

    def dispatch(self, request, *args, **kwargs):
        if is_admin(request.user):
            return redirect('core:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        return self.request.user

    def get_success_url(self):
        return reverse('users:profile')

    def form_valid(self, form):
        messages.success(self.request, 'Tu perfil se actualizó correctamente.')
        return super().form_valid(form)
