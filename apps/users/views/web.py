from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import views as auth_views
from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse, reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, FormView, ListView, UpdateView
from django.views.generic import TemplateView

from apps.core.permissions import is_admin

from ..forms import AddressForm, DeactivateAccountForm, LoginForm, ProfileForm, RegisterForm, TwoFactorCodeForm, TwoFactorDisableForm
from ..models import Address, City, Department, TwoFactorCode, User
from ..services import (
    GmailService,
    GmailServiceError,
    build_reactivation_url,
    disable_account,
    enable_account,
    notify_deactivation,
    pending_usable_two_factor_code,
    resolve_reactivation_token,
    send_two_factor_code,
)

PAUSED_USER_SESSION_KEY = 'paused_user_id'


def get_redirect_url(user):
    if user.is_staff or user.is_superuser:
        return 'core:dashboard'
    return 'catalog:home'


def get_paused_user(email, password):
    """Cuenta deshabilitada cuyas credenciales son correctas, o None.

    authenticate() rechaza las cuentas inactivas, así que la contraseña se
    comprueba a mano. Solo se revela el estado de la cuenta cuando la
    contraseña es correcta.
    """
    user = User.objects.filter(email__iexact=email).first()
    if user is None or user.is_active or not user.check_password(password):
        return None
    return user


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
                request.session.pop(PAUSED_USER_SESSION_KEY, None)
                messages.success(request, f'¡Bienvenida de nuevo, {user.first_name}!')
                return redirect(get_redirect_url(user))
            paused_user = get_paused_user(email, password)
            if paused_user is not None:
                request.session[PAUSED_USER_SESSION_KEY] = paused_user.pk
                return redirect('users:account_paused')
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
    def post(self, request):
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


class TwoFactorSetupView(LoginRequiredMixin, FormView):
    """Activa o desactiva la verificación en dos pasos por código de correo."""

    template_name = 'users/two_factor_setup.html'

    def dispatch(self, request, *args, **kwargs):
        if is_admin(request.user):
            return redirect('core:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['pending_code'] = pending_usable_two_factor_code(
            self.request.user, TwoFactorCode.Purpose.ENABLE,
        )
        context['code_digits'] = range(settings.TWO_FACTOR_CODE_LENGTH)
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        if not self.request.user.two_factor_enabled:
            kwargs['purpose'] = TwoFactorCode.Purpose.ENABLE
        return kwargs

    def get_form_class(self):
        if self.request.user.two_factor_enabled:
            return TwoFactorDisableForm
        return TwoFactorCodeForm

    def get(self, request, *args, **kwargs):
        if pending_usable_two_factor_code(request.user, TwoFactorCode.Purpose.ENABLE) is None:
            self._send_code(request)
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if 'resend' in request.POST:
            return self._send_code(request)
        if request.user.two_factor_enabled:
            return self._disable(request)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        user = self.request.user
        user.two_factor_enabled = True
        user.two_factor_enabled_at = timezone.now()
        user.save(update_fields=['two_factor_enabled', 'two_factor_enabled_at', 'updated_at'])
        messages.success(self.request, 'Activaste la verificación en dos pasos. Ya puedes deshabilitar tu cuenta.')
        return redirect('users:two_factor_setup')

    def _send_code(self, request):
        try:
            send_two_factor_code(request.user, TwoFactorCode.Purpose.ENABLE)
        except GmailServiceError:
            messages.error(request, 'No pudimos enviarte el código por correo. Inténtalo de nuevo.')
        else:
            messages.info(request, f'Te enviamos un código a {request.user.email}.')
        return redirect('users:two_factor_setup')

    def _disable(self, request):
        form = TwoFactorDisableForm(request.user, request.POST)
        if form.is_valid():
            user = request.user
            user.two_factor_enabled = False
            user.two_factor_enabled_at = None
            user.save(update_fields=['two_factor_enabled', 'two_factor_enabled_at', 'updated_at'])
            TwoFactorCode.objects.filter(user=user, used_at__isnull=True).delete()
            messages.success(request, 'Desactivaste la verificación en dos pasos.')
            return redirect('users:two_factor_setup')
        return self.render_to_response(self.get_context_data(form=form))


class AccountDeactivateView(LoginRequiredMixin, FormView):
    template_name = 'users/deactivate_account.html'
    form_class = DeactivateAccountForm
    success_url = reverse_lazy('core:home')

    def dispatch(self, request, *args, **kwargs):
        if is_admin(request.user):
            return redirect('core:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['pending_code'] = pending_usable_two_factor_code(
            self.request.user, TwoFactorCode.Purpose.DEACTIVATE,
        )
        context['code_digits'] = range(settings.TWO_FACTOR_CODE_LENGTH)
        return context

    def get(self, request, *args, **kwargs):
        if not request.user.two_factor_enabled:
            messages.info(
                request,
                'Antes de deshabilitar tu cuenta tienes que activar la verificación en dos pasos.',
            )
            return redirect('users:two_factor_setup')
        if pending_usable_two_factor_code(request.user, TwoFactorCode.Purpose.DEACTIVATE) is None:
            self._send_code(request)
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if not request.user.two_factor_enabled:
            messages.info(
                request,
                'Antes de deshabilitar tu cuenta tienes que activar la verificación en dos pasos.',
            )
            return redirect('users:two_factor_setup')
        if 'resend' in request.POST:
            self._send_code(request)
            return redirect('users:account_deactivate')
        return super().post(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def _send_code(self, request):
        try:
            send_two_factor_code(request.user, TwoFactorCode.Purpose.DEACTIVATE)
        except GmailServiceError:
            messages.error(request, 'No pudimos enviarte el código por correo. Inténtalo de nuevo.')
        else:
            messages.info(request, f'Te enviamos un código a {request.user.email}.')

    def form_valid(self, form):
        user = self.request.user
        disable_account(user, None)
        logout(self.request)
        if notify_deactivation(user, None, self.request):
            messages.success(
                self.request,
                'Tu cuenta fue deshabilitada. Te enviamos un correo con el enlace para reactivarla.',
            )
        else:
            messages.warning(
                self.request,
                f'Tu cuenta fue deshabilitada, pero no pudimos enviarte el correo con el enlace para reactivarla. Si deseas recuperarla, escribe a {settings.CARELY_EMAIL}.',
            )
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'No pudimos deshabilitar tu cuenta. Revisa los datos ingresados.')
        return super().form_invalid(form)


class PausedAccountView(FormView):
    """Cuenta deshabilitada con credenciales correctas: se reactiva con un código."""

    template_name = 'users/paused_account.html'
    form_class = TwoFactorCodeForm

    def get_paused_user(self):
        pk = self.request.session.get(PAUSED_USER_SESSION_KEY)
        if not pk:
            return None
        return User.objects.filter(pk=pk, is_active=False).first()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.get_paused_user()
        kwargs['purpose'] = TwoFactorCode.Purpose.REACTIVATE
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.get_paused_user()
        context['paused_user'] = user
        context['pending_code'] = pending_usable_two_factor_code(user, TwoFactorCode.Purpose.REACTIVATE)
        context['code_digits'] = range(settings.TWO_FACTOR_CODE_LENGTH)
        return context

    def get(self, request, *args, **kwargs):
        user = self.get_paused_user()
        if user is None:
            return redirect('users:login')
        if not user.was_deactivated_by_admin and pending_usable_two_factor_code(user, TwoFactorCode.Purpose.REACTIVATE) is None:
            self._send_code(request)
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        user = self.get_paused_user()
        if user is None or user.was_deactivated_by_admin:
            return redirect('users:login')
        if 'resend' in request.POST:
            self._send_code(request)
            return redirect('users:account_paused')
        return super().post(request, *args, **kwargs)

    def _send_code(self, request):
        user = self.get_paused_user()
        try:
            send_two_factor_code(user, TwoFactorCode.Purpose.REACTIVATE)
        except GmailServiceError:
            messages.error(request, 'No pudimos enviarte el código por correo. Inténtalo de nuevo.')
        else:
            messages.info(request, f'Te enviamos un código al correo {user.email}.')

    def form_valid(self, form):
        user = self.get_paused_user()
        enable_account(user)
        self.request.session.pop(PAUSED_USER_SESSION_KEY, None)
        messages.success(self.request, 'Tu cuenta fue reactivada. Ya puedes iniciar sesión.')
        return redirect('users:login')

    def form_invalid(self, form):
        messages.error(self.request, 'No pudimos reactivar tu cuenta. Revisa el código e inténtalo de nuevo.')
        return super().form_invalid(form)


class ReactivateAccountView(View):
    template_name = 'users/reactivate_account.html'

    def get(self, request, token):
        return render(request, self.template_name, self.get_context(token))

    def post(self, request, token):
        user = resolve_reactivation_token(token)
        if user is None:
            return render(request, self.template_name, self.get_context(token))
        enable_account(user)
        request.session.pop(PAUSED_USER_SESSION_KEY, None)
        messages.success(request, 'Tu cuenta fue reactivada. Ya puedes iniciar sesión.')
        return redirect('users:login')

    def get_context(self, token):
        """Un enlace vencido no es un 404: el usuario necesita saber qué pasó."""
        user = resolve_reactivation_token(token)
        return {'valid': user is not None, 'paused_user': user}


class AddressListView(LoginRequiredMixin, ListView):
    model = Address
    template_name = 'users/address_list.html'
    context_object_name = 'addresses'
    paginate_by = 6

    def get_queryset(self):
        return Address.objects.select_related('city__department').filter(
            user=self.request.user, is_active=True
        ).order_by('-is_default', '-created_at')


class AddressCreateView(LoginRequiredMixin, CreateView):
    model = Address
    form_class = AddressForm
    template_name = 'users/address_form.html'
    success_url = reverse_lazy('users:address_list')

    def form_valid(self, form):
        form.instance.user = self.request.user
        address = form.save()
        if not Address.objects.filter(user=self.request.user, is_active=True).exclude(pk=address.pk).filter(is_default=True).exists():
            address.is_default = True
            address.save(update_fields=['is_default'])
        messages.success(self.request, 'Dirección creada correctamente.')
        return redirect(self.success_url)


class AddressUpdateView(LoginRequiredMixin, UpdateView):
    model = Address
    form_class = AddressForm
    template_name = 'users/address_form.html'
    success_url = reverse_lazy('users:address_list')

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user, is_active=True)

    def form_valid(self, form):
        messages.success(self.request, 'Dirección actualizada correctamente.')
        return super().form_valid(form)


class AddressDeleteView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        addr = Address.objects.filter(user=request.user, is_active=True).get(pk=kwargs['pk'])
        addr.is_active = False
        addr.is_default = False
        addr.save(update_fields=['is_active', 'is_default'])
        messages.success(request, 'Dirección eliminada correctamente.')
        return redirect('users:address_list')


class AddressSetDefaultView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        addr = Address.objects.filter(user=request.user, is_active=True).get(pk=kwargs['pk'])
        from django.db import transaction
        with transaction.atomic():
            Address.objects.select_for_update().filter(
                user=request.user, is_default=True,
            ).update(is_default=False)
            addr.is_default = True
            addr.save(update_fields=['is_default'])
        messages.success(request, 'Dirección predeterminada actualizada.')
        return redirect('users:address_list')


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):

    def form_valid(self, form):
        response = super().form_valid(form)
        try:
            GmailService.send_password_reset_confirmation(form.user)
        except GmailServiceError:
            pass
        return response


class PasswordChangeView(auth_views.PasswordChangeView):

    def form_valid(self, form):
        response = super().form_valid(form)
        try:
            GmailService.send_password_reset_confirmation(self.request.user)
        except GmailServiceError:
            pass
        return response


def department_cities_api(request, department_pk):
    """Retorna los municipios de un departamento como JSON (id, name)."""
    if not Department.objects.filter(pk=department_pk).exists():
        raise Http404('Departamento no encontrado')
    cities = City.objects.filter(department_id=department_pk).values('id', 'name')
    return JsonResponse({'cities': list(cities)})
