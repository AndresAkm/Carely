from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path('admin/docs', include('django.contrib.admindocs.urls')),
    path('admin/', admin.site.urls),

    # Web
    path('', include('apps.core.urls')),
    path('accounts/', include('apps.users.urls')),
    path('catalogo/', include('apps.catalog.urls')),

    # API

    # Auth endpoints (login/logout de DRF)
    path('api/v1/auth/', include('rest_framework.urls')),

    # API Root — todos los endpoints unificados
    path('api/v1/', include('config.api_router')),
]


if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )