from django.urls import path

from .views import web

app_name = 'payments'

urlpatterns = [
    path('pedido/<int:order_id>/iniciar/', web.payment_start_view, name='start'),
    path('retorno/<int:payment_id>/', web.payment_return_view, name='return_page'),
    path('estado/<int:payment_id>/', web.payment_status_view, name='status'),
    path('webhook/wompi/', web.wompi_webhook_view, name='wompi_webhook'),
    # Solo se usa con PAYMENT_GATEWAY=simulado.
    path('simulado/<str:reference>/', web.simulated_checkout_view, name='simulated'),
    path(
        'simulado/<str:reference>/resolver/',
        web.simulated_result_view,
        name='simulated_result',
    ),
]