from smtplib import SMTPException

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse


class GmailServiceError(RuntimeError):
    """Indicates that Gmail could not accept an outgoing message."""


class GmailService:
    @staticmethod
    def send_message(subject, recipient, text_template, html_template, context):
        text_body = render_to_string(text_template, context).strip()
        html_body = render_to_string(html_template, context)
        message = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
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
