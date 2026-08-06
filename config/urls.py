from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path('admin/', admin.site.urls),

    # Web
    path('', include('apps.core.urls')),
    path('accounts/', include('apps.users.urls')),
    path('catalogo/', include('apps.catalog.urls')),

    # API
    
    # Auth endpoints (login/logout de DRF)
    path('api/v1/auth/', include('rest_framework.urls')),

    # Catalog endpoints
    path('api/v1/catalogo/', include('apps.catalog.urls_api')),

    # Users endpoints
    path('api/v1/usuarios/', include('apps.users.urls_api')),

    # Inventory endpoints
    path('api/v1/inventario/', include('apps.inventory.urls_api')),

    # Cart endpoints
    path('api/v1/carrito/', include('apps.cart.urls_api')),

    # Orders endpoints
    path('api/v1/pedidos/', include('apps.orders.urls_api')),

    # Payments endpoints
    path('api/v1/pagos/', include('apps.payments.urls_api')),
]


if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )