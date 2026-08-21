# API

La API usa Django REST Framework y JWT. La web mantiene autenticación mediante sesión.

## Rutas principales

| Método | URL | Vista | App |
|--------|-----|-------|-----|
| GET | `/` | `LandingView` | `apps.core` |
| GET | `/dashboard/` | `DashboardView` | `apps.core` |
| GET | `/dashboard/pedidos/` | `OrderListView` | `apps.orders` |
| GET | `/dashboard/pedidos/<id>/` | `OrderDetailView` | `apps.orders` |
| POST | `/dashboard/pedidos/<id>/estado/` | `OrderStatusUpdateView` | `apps.orders` |
| POST | `/dashboard/usuarios/forzar-eliminacion/` | `UserForceDeleteView` | `apps.users` |
| GET | `/dashboard/reportes/` | `ReportView` | `apps.core` |
| GET | `/dashboard/reportes/exportar/` | `ReportExportView` (PDF) | `apps.core` |
| GET | `/catalogo/` | `CatalogView` | `apps.catalog` |
| GET | `/catalogo/productos/<slug>/` | `ProductDetailView` | `apps.catalog` |
| GET/POST | `/accounts/login/` | `LoginView` | `apps.users` |
| GET/POST | `/accounts/register/` | `RegisterView` | `apps.users` |
| GET | `/accounts/register/confirmation/` | `RegistrationConfirmationView` | `apps.users` |
| POST | `/accounts/logout/` | `LogoutView` | `apps.users` |
| GET/POST | `/accounts/perfil/` | `ProfileView` | `apps.users` |
| GET | `/admin/` | Django Admin | `django.contrib.admin` |

## Convenciones

## Autenticación API

- `POST /api/v1/auth/token/` obtiene tokens JWT usando `username` y `password`.
- `POST /api/v1/auth/token/refresh/` renueva el token de acceso.
- Las peticiones protegidas deben enviar `Authorization: Bearer <access>`.

La recuperación web está disponible en `/accounts/password-reset/` y usa SMTP mediante las variables `EMAIL_*`. Solo se envían instrucciones a usuarios activos con contraseña utilizable.

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
