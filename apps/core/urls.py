from django.urls import path
from . import views
from .error_views import NotFoundView, PermissionDeniedView

app_name = 'core'

urlpatterns = [
    path('', views.LandingView.as_view(), name='home'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('privacidad/', views.LegalView.as_view(), name='privacy'),
    # Páginas de error. Solo accesibles con DEBUG=True; en producción las
    # sirve Django automáticamente al no encontrar una ruta (404) o cuando
    # una vista lanza PermissionDenied (403).
    path('errores/404/', NotFoundView.as_view(), name='error_404'),
    path('errores/403/', PermissionDeniedView.as_view(), name='error_403'),
]