from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.views.generic import TemplateView


class ErrorView(TemplateView):
    """Base de las páginas de error.

    Django solo resuelve `404.html` / `403.html` automáticamente cuando
    `DEBUG=False`, así que estas vistas existen para dos cosas: poder probar las
    páginas con el cliente de tests (que sí tiene DEBUG=False) y poder verlas en
    desarrollo con `DEBUG=True`.
    """

    status_code = 500

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        response.status_code = self.status_code
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # El enlace de "iniciar sesión" debe devolver al usuario a la página que
        # intentaba ver. `next` llega por query string cuando esta vista se usa
        # para previsualizar; en el 403 real de Django se usa `request.path`.
        context['next'] = self.request.GET.get('next') or self.request.get_full_path()
        return context


class NotFoundView(ErrorView):
    template_name = 'errors/404.html'
    status_code = 404


class PermissionDeniedView(ErrorView):
    template_name = 'errors/403.html'
    status_code = 403


def page_not_found(request, exception=None):
    """`handler404` de Django. Se usa con `DEBUG=False`."""
    raise Http404


def page_permission_denied(request, exception=None):
    """`handler403` de Django. Se usa con `DEBUG=False`."""
    raise PermissionDenied