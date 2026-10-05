from datetime import timedelta
from secrets import randbelow
from smtplib import SMTPException

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import EmailMultiAlternatives
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from .models import TwoFactorCode, User

REACTIVATION_SALT = 'carely.users.account_reactivation'
TWO_FACTOR_CODE_ERRORS = {
    'missing': 'Pide un código de verificación para continuar.',
    'invalid': 'El código no es correcto.',
    'expired': 'El código venció. Pide uno nuevo.',
    'locked': 'Demasiados intentos fallidos. Pide un código nuevo.',
}


class GmailServiceError(RuntimeError):
    """Indicates that Gmail could not accept an outgoing message."""


def build_reactivation_token(user):
    """Token firmado que viaja en el enlace de reactivación."""
    return TimestampSigner(salt=REACTIVATION_SALT).sign(str(user.pk))


def build_reactivation_url(request, user):
    return request.build_absolute_uri(
        reverse('users:account_reactivate', args=[build_reactivation_token(user)]),
    )


def resolve_reactivation_token(token):
    """Devuelve la cuenta deshabilitada a la que pertenece el enlace, o None.

    Las cuentas que deshabilitó un administrador no se reactivan desde el
    enlace: ese usuario tiene que escribir a soporte.
    """
    signer = TimestampSigner(salt=REACTIVATION_SALT)
    try:
        user_pk = signer.unsign(
            token, max_age=settings.ACCOUNT_REACTIVATION_TIMEOUT,
        )
    except (BadSignature, SignatureExpired):
        return None
    return User.objects.filter(
        pk=user_pk, is_active=False, deactivated_by__isnull=True,
    ).first()


def describe_reactivation_validity():
    """Traduce ACCOUNT_REACTIVATION_TIMEOUT a algo legible para el usuario."""
    seconds = settings.ACCOUNT_REACTIVATION_TIMEOUT
    if seconds >= 86400 and seconds % 86400 == 0:
        days = seconds // 86400
        return f'{days} días' if days > 1 else '1 día'
    hours = max(1, seconds // 3600)
    return f'{hours} horas'


class GmailService:
    @staticmethod
    def send_message(subject, recipient, text_template, html_template, context):
        recipients = [recipient] if isinstance(recipient, str) else list(recipient)
        text_body = render_to_string(text_template, context).strip()
        html_body = render_to_string(html_template, context)
        message = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients,
        )
        message.attach_alternative(html_body, 'text/html')
        try:
            return bool(message.send(fail_silently=False))
        except (SMTPException, OSError) as error:
            raise GmailServiceError('No fue posible enviar el correo mediante Gmail.') from error

    @classmethod
    def send_registration_confirmation(cls, user, request):
        context = {
            'user': user,
            'site_url': request.build_absolute_uri(reverse('catalog:home')),
        }
        return cls.send_message(
            subject='Tu cuenta Carely fue creada correctamente',
            recipient=user.email,
            text_template='users/registration_confirmation_email.txt',
            html_template='users/registration_confirmation_email.html',
            context=context,
        )

    @classmethod
    def send_password_reset_confirmation(cls, user):
        context = {
            'user': user,
            'login_url': reverse('users:login'),
        }
        return cls.send_message(
            subject='Tu contraseña de Carely fue actualizada',
            recipient=user.email,
            text_template='users/password_reset_confirmation_email.txt',
            html_template='users/password_reset_confirmation_email.html',
            context=context,
        )

    @classmethod
    def send_two_factor_code(cls, user, code):
        minutes = max(1, settings.TWO_FACTOR_CODE_TTL // 60)
        context = {
            'user': user,
            'code': code,
            'minutes': minutes,
        }
        return cls.send_message(
            subject='Tu código de verificación de Carely',
            recipient=user.email,
            text_template='users/two_factor_code_email.txt',
            html_template='users/two_factor_code_email.html',
            context=context,
        )

    @classmethod
    def send_account_deactivated(cls, user, reactivation_url=None):
        context = {
            'user': user,
            'reactivation_url': reactivation_url,
            'reactivation_validity': describe_reactivation_validity(),
            'carely_email': settings.CARELY_EMAIL,
        }
        return cls.send_message(
            subject='Tu cuenta Carely fue deshabilitada',
            recipient=user.email,
            text_template='users/account_deactivated_email.txt',
            html_template='users/account_deactivated_email.html',
            context=context,
        )

    @classmethod
    def send_account_deactivated_notice(cls, user, actor):
        context = {
            'user': user,
            'actor': actor,
            'deactivated_at': user.deactivated_at,
        }
        return cls.send_message(
            subject=f'Cuenta deshabilitada: {user.email}',
            recipient=settings.CARELY_EMAIL,
            text_template='users/account_deactivated_notice_email.txt',
            html_template='users/account_deactivated_notice_email.html',
            context=context,
        )


def describe_actor(actor):
    if actor is None:
        return 'El titular de la cuenta'
    return actor.get_full_name() or actor.email


def disable_account(user, actor):
    """Marca la cuenta como deshabilitada y deja rastro de quién lo hizo.

    `actor` es None cuando la deshabilitó el propio titular.
    """
    user.is_active = False
    user.deactivated_at = timezone.now()
    user.deactivated_by = actor
    user.save()


def enable_account(user):
    """Reactiva la cuenta y limpia el rastro de la deshabilitación."""
    user.is_active = True
    user.deactivated_at = None
    user.deactivated_by = None
    user.save()


def notify_deactivation(user, actor, request):
    """Avisa al titular y a soporte. Devuelve False si el correo no salió.

    El aviso es una cortesía: si falla, la cuenta queda deshabilitada igual.
    """
    try:
        reactivation_url = None
        if actor is None:
            reactivation_url = build_reactivation_url(request, user)
        GmailService.send_account_deactivated(user, reactivation_url)
        GmailService.send_account_deactivated_notice(user, describe_actor(actor))
    except GmailServiceError:
        return False
    return True


def send_two_factor_code(user, purpose):
    """Genera un código nuevo, invalida los anteriores y lo envía al correo."""
    TwoFactorCode.objects.filter(user=user, purpose=purpose, used_at__isnull=True).delete()
    code = f'{randbelow(10 ** settings.TWO_FACTOR_CODE_LENGTH):0{settings.TWO_FACTOR_CODE_LENGTH}d}'
    TwoFactorCode.objects.create(
        user=user,
        purpose=purpose,
        code_hash=make_password(code),
        expires_at=timezone.now() + timedelta(seconds=settings.TWO_FACTOR_CODE_TTL),
    )
    GmailService.send_two_factor_code(user, code)
    return code


def consume_two_factor_code(user, purpose, code):
    """Valida un código de un solo uso. Devuelve None o el mensaje de error."""
    submitted = (code or '').strip()
    if not submitted:
        return TWO_FACTOR_CODE_ERRORS['missing']
    two_factor_code = pending_two_factor_code(user, purpose)
    if two_factor_code is None:
        return TWO_FACTOR_CODE_ERRORS['missing']
    if two_factor_code.is_locked:
        return TWO_FACTOR_CODE_ERRORS['locked']
    if check_password(submitted, two_factor_code.code_hash):
        if two_factor_code.is_expired:
            return TWO_FACTOR_CODE_ERRORS['expired']
        two_factor_code.mark_as_used()
        return None
    two_factor_code.register_failed_attempt()
    if two_factor_code.is_locked:
        return TWO_FACTOR_CODE_ERRORS['locked']
    return TWO_FACTOR_CODE_ERRORS['invalid']


def pending_two_factor_code(user, purpose):
    """Código vigente del usuario, o None si tiene que pedir uno nuevo."""
    return TwoFactorCode.objects.filter(
        user=user, purpose=purpose, used_at__isnull=True,
    ).first()


def pending_usable_two_factor_code(user, purpose):
    """Igual que pending_two_factor_code, pero descarta el vencido o bloqueado."""
    two_factor_code = pending_two_factor_code(user, purpose)
    return two_factor_code if (two_factor_code and two_factor_code.is_usable) else None
