import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.catalog.models import Product

from ..services import CartStockError, add_item, get_cart_context, remove_item, update_item_quantity


@login_required
def cart_view(request):
    """Vista principal del carrito."""
    context = get_cart_context(request.user)
    return render(request, 'cart/cart.html', context)


@login_required
@require_POST
def cart_add(request, product_pk):
    """
    Agrega un producto al carrito.
    Acepta JSON (fetch) o form POST normal.
    Responde JSON si petición es AJAX (Accept: application/json o header X-Requested-With).
    """
    product = get_object_or_404(Product, pk=product_pk, is_active=True)
    is_ajax = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
    )

    quantity = 1
    if request.content_type == 'application/json':
        try:
            body = json.loads(request.body)
            quantity = int(body.get('quantity', 1))
        except (json.JSONDecodeError, ValueError):
            quantity = 1
    else:
        try:
            quantity = int(request.POST.get('quantity', 1))
        except (ValueError, TypeError):
            quantity = 1

    try:
        item = add_item(request.user, product, quantity)
        if is_ajax:
            from ..services import get_cart_context
            ctx = get_cart_context(request.user)
            return JsonResponse({
                'ok': True,
                'message': f'"{product.name}" añadido al carrito.',
                'cart_count': ctx['cart_count'],
                'item_quantity': item.quantity,
            })
        messages.success(request, f'"{product.name}" añadido al carrito.')
    except CartStockError as e:
        if is_ajax:
            return JsonResponse({'ok': False, 'message': str(e)}, status=400)
        messages.error(request, str(e))
    except ValueError as e:
        if is_ajax:
            return JsonResponse({'ok': False, 'message': str(e)}, status=400)
        messages.error(request, str(e))

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'cart:cart'
    return redirect(next_url)


@login_required
@require_POST
def cart_update(request, product_pk):
    """
    Actualiza la cantidad de un item del carrito.
    Acepta JSON o form POST.
    """
    product = get_object_or_404(Product, pk=product_pk, is_active=True)
    is_ajax = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
    )

    try:
        if request.content_type == 'application/json':
            body = json.loads(request.body)
            quantity = int(body.get('quantity', 1))
        else:
            quantity = int(request.POST.get('quantity', 1))
    except (json.JSONDecodeError, ValueError, TypeError):
        quantity = 1

    try:
        item = update_item_quantity(request.user, product, quantity)
        if is_ajax:
            from ..services import get_cart_context
            ctx = get_cart_context(request.user)
            return JsonResponse({
                'ok': True,
                'item_quantity': item.quantity if item else 0,
                'item_subtotal': str(item.subtotal) if item else '0',
                'cart_total': str(ctx['cart_total']),
                'cart_count': ctx['cart_count'],
                'removed': item is None,
            })
        if item is None:
            messages.info(request, f'"{product.name}" eliminado del carrito.')
        else:
            messages.success(request, 'Cantidad actualizada.')
    except CartStockError as e:
        if is_ajax:
            return JsonResponse({'ok': False, 'message': str(e)}, status=400)
        messages.error(request, str(e))

    return redirect('cart:cart')


@login_required
@require_POST
def cart_remove(request, product_pk):
    """Elimina completamente un item del carrito."""
    product = get_object_or_404(Product, pk=product_pk)
    is_ajax = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
    )

    removed = remove_item(request.user, product)
    if is_ajax:
        from ..services import get_cart_context
        ctx = get_cart_context(request.user)
        return JsonResponse({
            'ok': True,
            'message': f'"{product.name}" eliminado del carrito.',
            'cart_count': ctx['cart_count'],
            'cart_total': str(ctx['cart_total']),
        })

    if removed:
        messages.info(request, f'"{product.name}" eliminado del carrito.')
    return redirect('cart:cart')
