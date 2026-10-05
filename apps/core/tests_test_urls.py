"""URLconf solo para tests: fuerza un 403 real de Django.

Verifica que `templates/403.html` se usa cuando una vista lanza
`PermissionDenied`, que es el camino que sigue la web en producción
(DEBUG=False). Django solo busca `403.html` en la raíz de los directorios de
templates, no en `errors/`.
"""

from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.urls import include, path


def vista_protegida(request):
    raise PermissionDenied


def vista_inexistente(request):
    raise Http404


def vista_falla(request):
    raise ValueError('Fallo deliberado para probar el manejo de errores.')


# Las apps se incluyen para que los context processors puedan inyectar
# `carely_email` y `site_name` en la página de error.
urlpatterns = [
    path('accounts/', include('apps.users.urls')),
    path('catalogo/', include('apps.catalog.urls')),
    path('', include('apps.core.urls')),
    path('protegida/', vista_protegida),
    path('ruta-que-no-existe/', vista_inexistente),
    path('falla/', vista_falla),
]