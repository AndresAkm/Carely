from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView


urlpatterns = [
        # API Schema & Documentation
    path('api/v1/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/v1/swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/v1/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    path('admin/docs/', include('django.contrib.admindocs.urls')),
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