from django.conf import settings

from apps.core.error_views import NotFoundView, PermissionDeniedView

# Rutas que nunca deben recibir una página HTML de error: la API espera JSON
# y los estáticos/media los sirve el servidor de desarrollo.
EXENT_PATHS = ('/api/', '/static/', '/media/')


class CarelyErrorPagesMiddleware:
    """Muestra las páginas de error de Carely incluso con `DEBUG=True`.

    Con `DEBUG=True` Django ignora `404.html` y `403.html` y devuelve su propia
    página técnica de depuración (ver `django.core.handlers.exception`).
    Eso es útil para ver tracebacks, pero deja el mensaje en inglés con la lista
    de patrones de URL.

    Este middleware solo intercepta respuestas 403 y 404 que ya se generaron y
    las vuelve a pintar con la plantilla de Carely. Los errores 500 no se tocan:
    la página técnica de traceback es justo lo que se quiere en desarrollo.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not settings.DEBUG or response.status_code not in (403, 404):
            return response
        if not self._debe_usar_pagina_html(request):
            return response
        view = NotFoundView if response.status_code == 404 else PermissionDeniedView
        branded = view.as_view()(request)
        # Este middleware es el más externo de la cadena, así que nada va a
        # renderizar la respuesta por nosotros: hay que hacerlo aquí.
        if hasattr(branded, 'render') and callable(branded.render):
            branded = branded.render()
        return branded

    def _debe_usar_pagina_html(self, request):
        if request.path.startswith(EXENT_PATHS):
            return False
        accept = request.headers.get('Accept', '')
        if 'application/json' in accept and 'text/html' not in accept:
            return False
        return True