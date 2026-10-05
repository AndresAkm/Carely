# API

La API usa Django REST Framework y JWT. La web mantiene autenticación mediante sesión.

La documentación interactiva se genera con drf-spectacular:

- `/api/v1/schema/` — esquema OpenAPI
- `/api/v1/swagger/` — Swagger UI
- `/api/v1/redoc/` — ReDoc

## Autenticación API

- `POST /api/v1/auth/token/` obtiene tokens JWT usando `username` y `password`.
- `POST /api/v1/auth/token/refresh/` renueva el token de acceso.
- `POST /api/v1/auth/login/` y `POST /api/v1/auth/logout/` (sesión DRF).
- Las peticiones protegidas deben enviar `Authorization: Bearer <access>`.

La recuperación web está disponible en `/accounts/password-reset/` y usa SMTP mediante las variables `EMAIL_*`. Solo se envían instrucciones a usuarios activos con contraseña utilizable.

## Endpoints REST

ViewSets registrados en `config/api_router.py`, bajo el prefijo `/api/v1/`:

| Prefijo | ViewSet | Permisos | Notas |
|---------|---------|----------|-------|
| `catalogo/productos/` | `ProductViewSet` | `IsAdminOrReadOnly` | CRUD completo |
| `catalogo/categorias/` | `CategoryViewSet` | `IsAdminOrReadOnly` | CRUD completo |
| `usuarios/` | `UserViewSet` | `IsAdminOnly` | Sin `DELETE` (`http_method_names`) |
| `direcciones/` | `AddressViewSet` | `IsAuthenticatedOwnedOrAdmin` | `PATCH /<id>/establecer-predeterminada/` |
| `geo/departamentos/` | `DepartmentViewSet` | lectura | Departamentos de Colombia |
| `geo/municipios/` | `CityViewSet` | lectura | Filtro `?department=<id>` |
| `inventario/movimientos/` | `InventoryMovementViewSet` | `IsAdminOnly` | `@action` POST `entrada/`, `salida/`, `ajuste/` |
| `carrito/carritos/` | `CartViewSet` | `IsAuthenticatedOrAdminReadOnly` | Un carrito por usuario |
| `carrito/items/` | `CartItemViewSet` | `IsAuthenticatedOrAdminReadOnly` | Único por carrito + producto |
| `pedidos/pedidos/` | `OrderViewSet` | `IsAuthenticatedOrAdminReadOnly` | CRUD |
| `pedidos/items/` | `OrderItemViewSet` | `IsAuthenticatedOrAdminReadOnly` | CRUD |
| `pagos/` | `PaymentViewSet` | `IsAuthenticatedOrAdminReadOnly` | CRUD |

## Rutas web

### Catálogo y landing

| Método | URL | Vista | App |
|--------|-----|-------|-----|
| GET | `/` | `LandingView` | `apps.core` |
| GET | `/privacidad/` | `LegalView` | `apps.core` |
| GET | `/catalogo/` | `CatalogView` | `apps.catalog` |
| GET | `/catalogo/productos/<slug>/` | `ProductDetailView` | `apps.catalog` |

### Cuentas

| Método | URL | Vista |
|--------|-----|-------|
| GET/POST | `/accounts/login/` | `LoginView` |
| GET/POST | `/accounts/register/` | `RegisterView` |
| GET | `/accounts/register/confirmation/` | `RegistrationConfirmationView` |
| POST | `/accounts/logout/` | `LogoutView` |
| GET/POST | `/accounts/perfil/` | `ProfileView` |
| GET/POST | `/accounts/verificacion-dos-pasos/` | `TwoFactorSetupView` |
| GET/POST | `/accounts/deshabilitar-cuenta/` | `AccountDeactivateView` |
| GET/POST | `/accounts/cuenta-pausada/` | `PausedAccountView` |
| GET/POST | `/accounts/reactivar-cuenta/<token>/` | `ReactivateAccountView` |
| GET/POST | `/accounts/password-change/` | `PasswordChangeView` |
| GET | `/accounts/password-change/done/` | `PasswordChangeDoneView` |
| GET/POST | `/accounts/password-reset/` | `PasswordResetView` |
| GET | `/accounts/password-reset/done/` | `PasswordResetDoneView` |
| GET/POST | `/accounts/password-reset/<uidb64>/<token>/` | `PasswordResetConfirmView` |
| GET | `/accounts/password-reset/complete/` | `PasswordResetCompleteView` |

### Direcciones del usuario

| Método | URL | Vista |
|--------|-----|-------|
| GET | `/accounts/direcciones/` | `AddressListView` |
| GET/POST | `/accounts/direcciones/nueva/` | `AddressCreateView` |
| GET/POST | `/accounts/direcciones/<pk>/editar/` | `AddressUpdateView` |
| POST | `/accounts/direcciones/<pk>/eliminar/` | `AddressDeleteView` |
| POST | `/accounts/direcciones/<pk>/predeterminada/` | `AddressSetDefaultView` |
| GET | `/accounts/municipios/departamento/<pk>/` | `department_cities_api` (JSON) |

### Carrito

| Método | URL | Vista |
|--------|-----|-------|
| GET | `/carrito/` | `cart_view` |
| POST | `/carrito/agregar/<product_pk>/` | `cart_add` |
| POST | `/carrito/actualizar/<product_pk>/` | `cart_update` |
| POST | `/carrito/eliminar/<product_pk>/` | `cart_remove` |

`cart_add`, `cart_update` y `cart_remove` aceptan `Accept: application/json` y
responden JSON, lo que consume `static/js/main.js` para el carrito AJAX.

### Pedidos

| Método | URL | Vista |
|--------|-----|-------|
| GET/POST | `/pedidos/checkout/` | `checkout_view` |
| GET | `/pedidos/exito/<order_id>/` | `order_success_view` |
| GET | `/pedidos/` | `order_list_view` |
| GET | `/pedidos/<order_id>/` | `order_detail_view` |
| GET | `/pedidos/cupones/validar/` | `validate_coupon_ajax` (JSON) |

### Dashboard (solo administradores)

| Método | URL | Vista |
|--------|-----|-------|
| GET | `/dashboard/` | `DashboardView` |
| GET | `/dashboard/pedidos/` | `OrderListView` |
| GET | `/dashboard/pedidos/<pk>/` | `OrderDetailView` |
| POST | `/dashboard/pedidos/<pk>/estado/` | `OrderStatusUpdateView` |
| POST | `/dashboard/pedidos/<pk>/avanzar/` | `OrderAdvanceStatusView` |
| POST | `/dashboard/pedidos/<pk>/cancelar/` | `OrderCancelView` |
| POST | `/dashboard/pedidos/<pk>/notas/` | `OrderUpdateNotesView` |
| GET | `/dashboard/reportes/` | `ReportView` |
| GET | `/dashboard/reportes/exportar/` | `ReportExportView` (PDF) |
| GET | `/dashboard/productos/` | `ProductListView` |
| GET/POST | `/dashboard/productos/nuevo/` | `ProductCreateView` |
| GET/POST | `/dashboard/productos/<pk>/editar/` | `ProductUpdateView` |
| POST | `/dashboard/productos/<pk>/eliminar/` | `ProductDeleteView` |
| GET | `/dashboard/categorias/` | `CategoryListView` |
| GET/POST | `/dashboard/categorias/nueva/` | `CategoryCreateView` |
| GET/POST | `/dashboard/categorias/<pk>/editar/` | `CategoryUpdateView` |
| POST | `/dashboard/categorias/<pk>/eliminar/` | `CategoryDeleteView` |
| GET | `/dashboard/usuarios/` | `UserListView` |
| GET/POST | `/dashboard/usuarios/nuevo/` | `UserCreateView` |
| POST | `/dashboard/usuarios/forzar-eliminacion/` | `UserForceDeleteView` |
| GET/POST | `/dashboard/usuarios/<pk>/editar/` | `UserUpdateView` |
| GET/POST | `/dashboard/usuarios/<pk>/password/` | `UserPasswordChangeView` |
| POST | `/dashboard/usuarios/<pk>/estado/` | `UserToggleActiveView` |
| GET | `/dashboard/direcciones/` | `AddressListView` |
| GET/POST | `/dashboard/direcciones/nueva/` | `AddressCreateView` |
| GET/POST | `/dashboard/direcciones/<pk>/editar/` | `AddressUpdateView` |
| POST | `/dashboard/direcciones/<pk>/estado/` | `AddressToggleActiveView` |
| GET | `/dashboard/cupones/` | `CouponListView` |
| GET/POST | `/dashboard/cupones/nuevo/` | `CouponCreateView` |
| GET/POST | `/dashboard/cupones/<pk>/editar/` | `CouponUpdateView` |
| POST | `/dashboard/cupones/<pk>/estado/` | `CouponToggleActiveView` |
| POST | `/dashboard/cupones/<pk>/eliminar/` | `CouponDeleteView` |

### Django

| Método | URL | Vista |
|--------|-----|-------|
| — | `/admin/` | Django Admin |
| — | `/admin/docs/` | admindocs |

## Convenciones

- Namespaces de URL: `core`, `catalog`, `users`, `cart`, `orders`, `dashboard`.
- Autenticación web: `login_required` y `UserPassesTestMixin` con `is_admin`.
- Rutas de redirects configuradas en `config/settings/base.py`:
  - `LOGIN_URL = 'users:login'`
  - `LOGIN_REDIRECT_URL = 'core:dashboard'`
  - `LOGOUT_REDIRECT_URL = 'core:home'`

## Agregar un endpoint

1. Definir la vista en `apps/<app>/views/` (web) o `apps/<app>/views/api.py` (REST).
2. Registrar el patrón en `apps/<app>/urls.py` o en `config/api_router.py`.
3. Incluir el `urls.py` de la app en `config/urls.py` si es una raíz nueva.
4. Para ViewSets, declarar permisos en `apps/core/permissions.py` y documentar el
   endpoint en `docs/api.md`.