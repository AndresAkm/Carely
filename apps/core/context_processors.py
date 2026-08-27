def site_settings(request):
    return {
        'site_name': 'Carely',
        'site_description': 'Tu tienda de cuidado personal de confianza',
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
