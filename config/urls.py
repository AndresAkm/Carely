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

    # Endpoint base
    
    # Catalog endpoints
    path('api/v1/catalogo/', include('apps.catalog.urls_api')),

    # Users endpoints
    path('api/v1/usuarios/', include('apps.users.urls_api')),
]


if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )