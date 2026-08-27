from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from apps.users.models import Address
from apps.cart.services import get_cart_context
from apps.orders.services import checkout_cart, EmptyCartError, InvalidAddressError
from apps.inventory.services import InsufficientStockError


@login_required
def checkout_view(request):
    """
    Vista para el checkout web.
    Permite seleccionar una dirección activa del usuario y resumir la compra.
    Procesa el POST de forma segura y transforma el carrito en un pedido (Order).
    """
    context = get_cart_context(request.user)
    
    if not context.get('cart_items'):
        messages.warning(request, 'Tu carrito está vacío. Agrega productos para poder proceder al pago.')
        return redirect('cart:cart')
    
    addresses = Address.objects.filter(user=request.user, is_active=True).order_by('-is_default', '-created_at')
    
    if request.method == 'POST':
        address_id = request.POST.get('address_id')
        try:
            order = checkout_cart(request.user, int(address_id), notes=request.POST.get('notes', ''))
            messages.success(request, f'¡Pedido #{order.id} confirmado con éxito!')
            return redirect('orders:success', order_id=order.id)
            
        except InvalidAddressError as e:
            messages.error(request, str(e))
        except InsufficientStockError as e:
            messages.error(request, f'No pudimos procesar el pedido. {str(e)}')
            return redirect('cart:cart')
        except EmptyCartError as e:
            messages.error(request, str(e))
            return redirect('cart:cart')
        except ValueError:
            messages.error(request, 'Selecciona una dirección de envío válida.')
        except Exception as e:
            messages.error(request, 'Ocurrió un error inesperado al procesar el pedido.')
            
    context['addresses'] = addresses
    return render(request, 'orders/checkout.html', context)


@login_required
def order_success_view(request, order_id):
    from apps.orders.models import Order
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'orders/success.html', {'order': order})


@login_required
def order_list_view(request):
    """
    Lista todos los pedidos propios del usuario autenticado.
    No permite acceder a pedidos ajenos ni modificar.
    """
    from apps.orders.models import Order
    orders = Order.objects.filter(user=request.user).order_by('-created_at').prefetch_related('items')
    return render(request, 'orders/order_list.html', {'orders': orders})


@login_required
def order_detail_view(request, order_id):
    """
    Ver un pedido en detalle por ID.
    El get_object_or_404 filtra por el request.user (aislamiento).
    """
    from apps.orders.models import Order
    order = get_object_or_404(
        Order.objects.select_related('user').prefetch_related('items__product', 'items__product__category'),
        id=order_id, 
        user=request.user
    )
    return render(request, 'orders/order_detail.html', {'order': order})
