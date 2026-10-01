from django.conf import settings


def site_settings(request):
    return {
        'site_name': settings.SITE_NAME,
        'site_description': settings.SITE_DESCRIPTION,
        'carely_email': settings.CARELY_EMAIL,
        'carely_phone': settings.CARELY_PHONE,
        'carely_phone_href': settings.CARELY_PHONE_HREF,
        'carely_address': settings.CARELY_ADDRESS,
        'carely_socials': settings.CARELY_SOCIALS,
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