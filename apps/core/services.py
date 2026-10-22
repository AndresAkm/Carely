import logging

from django.conf import settings

from apps.users.services import GmailService, GmailServiceError

logger = logging.getLogger(__name__)


def send_contact_message(name: str, email: str, subject: str, message: str) -> None:
    """Reenvía el mensaje del formulario de contacto al equipo de Carely.

    Primero avisa al equipo (envío crítico: si falla, se propaga el error para
    que la vista le diga al usuario que reintente). Después acusa recibo al
    remitente; ese correo es una cortesía, así que si falla solo se registra y
    la operación se considera exitosa.
    """
    context = {
        'name': name,
        'email': email,
        'subject': subject,
        'message': message,
        'carely_email': settings.CARELY_EMAIL,
    }
    GmailService.send_message(
        subject=f'Nuevo contacto: {subject or name}',
        recipient=settings.CARELY_EMAIL,
        text_template='core/emails/contact_message.txt',
        html_template='core/emails/contact_message.html',
        context=context,
    )
    try:
        GmailService.send_message(
            subject='Recibimos tu mensaje - Carely',
            recipient=email,
            text_template='core/emails/contact_confirmation.txt',
            html_template='core/emails/contact_confirmation.html',
            context=context,
        )
    except GmailServiceError:
        logger.warning('No se pudo enviar la confirmación de contacto a %s', email)


def send_contact_reply(contact_request, reply: str, admin) -> bool:
    """Envía la respuesta del panel al correo de quien hizo la solicitud.

    El remitente técnico es el de la configuración de correo, pero se responde
    a la dirección del administrador que atendió la solicitud.
    """
    context = {
        'name': contact_request.name,
        'email': contact_request.email,
        'subject': contact_request.subject,
        'message': contact_request.message,
        'reply': reply,
        'admin': admin,
        'carely_email': settings.CARELY_EMAIL,
    }
    subject = f'Re: {contact_request.subject}' if contact_request.subject else 'Respuesta de Carely'
    return GmailService.send_message(
        subject=subject,
        recipient=contact_request.email,
        text_template='core/emails/contact_reply.txt',
        html_template='core/emails/contact_reply.html',
        context=context,
        reply_to=[admin.email] if admin and admin.email else None,
    )
