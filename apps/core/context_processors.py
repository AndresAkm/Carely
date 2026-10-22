import re

from django.conf import settings

from apps.core.models import SiteCustomization


def phone_href(phone):
    """`+57 323 227 3483` -> `+573232273483`, el formato de `tel:`."""
    return '+' + re.sub(r'\D', '', phone)


def site_settings(request):
    """Datos públicos de la tienda para el pie de página.

    Un campo guardado en el panel gana al valor de `settings` (variables de
    entorno). Un campo vacío en el panel usa el valor del servidor, así que
    borrar un dato no lo deja sin mostrar.
    """
    config = SiteCustomization.load()
    socials = settings.CARELY_SOCIALS
    return {
        'site_name': settings.SITE_NAME,
        'site_description': settings.SITE_DESCRIPTION,
        'carely_email': config.footer_email or settings.CARELY_EMAIL,
        'carely_phone': config.footer_phone or settings.CARELY_PHONE,
        'carely_phone_href': phone_href(config.footer_phone) if config.footer_phone else settings.CARELY_PHONE_HREF,
        'carely_address': config.footer_address or settings.CARELY_ADDRESS,
        'carely_socials': {
            'facebook': config.footer_facebook or socials.get('facebook', ''),
            'instagram': config.footer_instagram or socials.get('instagram', ''),
            'whatsapp': config.footer_whatsapp or socials.get('whatsapp', ''),
        },
        'site_logo_url': config.get_logo_url(),
        'site_logo_icon_url': config.get_logo_icon_url(),
    }


def footer_categories(request):
    """
    Inyecta `categories` (QS de categorías activas) en cada template.

    El footer itera sobre `categories`, que solo recibían las vistas de home y
    catálogo; en el resto de páginas el bloque salía vacío.
    """
    from apps.catalog.models import Category

    return {
        'categories': Category.objects.filter(is_active=True),
    }


def cart_count(request):
    """
    Inyecta `cart_count` (int) en cada template.
    Devuelve 0 si el usuario no está autenticado o no tiene carrito.
    Usa una única query COUNT eficiente.
    """
    count = 0
    if request.user.is_authenticated:
        try:
            from django.db.models import Sum
            from apps.cart.models import CartItem
            result = (
                CartItem.objects
                .filter(cart__user=request.user)
                .aggregate(total=Sum('quantity'))
            )
            count = result['total'] or 0
        except Exception:
            count = 0
    return {'cart_count': count}