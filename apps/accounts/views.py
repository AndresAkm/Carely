from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.shortcuts import render, redirect
from django.views import View
from .forms import LoginForm, RegisterForm


def get_redirect_url(user):
    if user.is_staff or user.is_superuser:
        return 'dashboard:home'
    return 'landing:catalog'


class LoginView(View):
    template_name = 'accounts/login.html'

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
    template_name = 'accounts/register.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect(get_redirect_url(request.user))
        form = RegisterForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, 'Tu cuenta se ha creado correctamente. ¡Bienvenida a Carely!')
            login(request, user)
            return redirect(get_redirect_url(user))
        return render(request, self.template_name, {'form': form})


class LogoutView(View):
    def get(self, request):
        logout(request)
        messages.success(request, 'Has cerrado sesión correctamente.')
        return redirect('landing:home')
