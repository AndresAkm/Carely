# API

El proyecto usa las vistas de Django (sin DRF por ahora). La API se expone vía URL patterns y formularios tradicionales.

## Rutas principales

| Método | URL | Vista | App |
|--------|-----|-------|-----|
| GET | `/` | `LandingView` | `apps.core` |
| GET | `/dashboard/` | `DashboardView` | `apps.core` |
| GET | `/catalogo/` | `CatalogView` | `apps.catalog` |
| GET/POST | `/accounts/login/` | `LoginView` | `apps.users` |
| GET/POST | `/accounts/register/` | `RegisterView` | `apps.users` |
| POST | `/accounts/logout/` | `LogoutView` | `apps.users` |
| GET | `/admin/` | Django Admin | `django.contrib.admin` |

## Convenciones

- Namespaces de URL: `core`, `catalog`, `users`.
- Autenticación: `login_required` y `staff_member_required` en vistas protegidas.
- Rutas de redirects configuradas en `config/settings/base.py`:
  - `LOGIN_URL = 'users:login'`
  - `LOGIN_REDIRECT_URL = 'core:dashboard'`
  - `LOGOUT_REDIRECT_URL = 'core:home'`

## Agregar un endpoint

1. Definir la vista en `apps/<app>/views.py`.
2. Registrar el patrón en `apps/<app>/urls.py`.
3. Incluir el `urls.py` de la app en `config/urls.py`.
