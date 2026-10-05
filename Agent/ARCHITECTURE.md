# Arquitectura

Mapa del proyecto: qué existe, dónde vive y cómo se relaciona. Todo lo de aquí
fue verificado contra el código, no es aspiracional.

## Stack

| Pieza | Versión | Nota |
|---|---|---|
| Python | 3.12+ | |
| Django | 6.x (`>=6.0,<7.0`) | |
| DRF | `>=3.17,<4.0` | API REST |
| drf-spectacular | `>=0.30` | Esquema OpenAPI |
| simplejwt | `>=5.5` | Autenticación JWT |
| PyMySQL | `>=1.1` | Driver MySQL/MariaDB |
| reportlab | `>=4.0` | Exportes PDF |
| Pillow | `>=10` | Imágenes |
| django-storages + boto3 | | S3 (Supabase) opcional |

Base de datos: **MySQL** por defecto; SQLite solo en `test`.

## Árbol

```
config/
├── settings/          base.py + development.py + test.py + production.py
├── urls.py            raíz web + /api/v1/ + schema + admin
├── api_router.py      los 12 ViewSets de la API
├── wsgi.py / asgi.py
├── api.py             instancia de DRF
apps/
├── core/              home, legal, dashboard, reportes, permisos, context processors
├── users/             User custom, direcciones, geo (Colombia), auth web+API
├── catalog/           Category, Product
├── cart/              Cart, CartItem
├── orders/            Order, OrderItem, Coupon, OrderStatusHistory
├── inventory/         InventoryMovement
├── payments/          Payment
templates/             base.html, navbar, footer, messages, components/
static/                css/ js/ compartidos
docs/                  api.md, database.md, deployment.md
requirements/          base.txt, development.txt, production.txt
```

## Las 7 apps

| App | Modelos | Web | API | Tests |
|---|---|---|---|---|
| `core` | — | home, `/privacidad/`, dashboard, reportes | — | 18 |
| `users` | `User`, `Address`, `Department`, `City` | login, registro, perfil, direcciones, desactivar cuenta | `UserViewSet`, `AddressViewSet`, `DepartmentViewSet`, `CityViewSet` | 68 |
| `catalog` | `Category`, `Product` | catálogo, detalle, dashboard | `ProductViewSet`, `CategoryViewSet` | **0** ⚠ |
| `cart` | `Cart`, `CartItem` | ver/añadir/actualizar/quitar | `CartViewSet`, `CartItemViewSet` | 29 |
| `orders` | `Order`, `OrderItem`, `OrderStatusHistory`, `Coupon` | checkout, mis pedidos, dashboard | `OrderViewSet`, `OrderItemViewSet` | 35 |
| `inventory` | `InventoryMovement` | — | `InventoryMovementViewSet` | 31 |
| `payments` | `Payment` | — | `PaymentViewSet` | **0** ⚠ |

⚠ `catalog` no tiene archivo `tests.py` y `payments/tests.py` está vacío. El
detalle de producto, que es una vista con formulario de compra, se prueba desde
`apps/core/tests.py`. Si tocas catálogo o pagos, **crea el archivo de tests que
falta**.

## Modelos

Convenciones, aplicadas de forma casi uniforme:

- `verbose_name` en español en todos los campos.
- `related_name` explícito en cada `ForeignKey`.
- Sin `db_table`: se usa el nombre por defecto de Django.
- `created_at` / `updated_at` con `auto_now_add` / `auto_now` en las entidades
  principales. `OrderItem` y `CartItem` **no** los tienen.
- Slug autogenerado en `save()` con `slugify` para `Category` y `Product`.
- Borrado lógico solo en `Address` (`is_active`). El resto usa `on_delete`
  explícito: `PROTECT` para datos geográficos, `CASCADE` para dependientes.

### User

`apps/users/models.py` extiende `AbstractUser` con:

- `email` único (y `username = email` por convención)
- `phone`, `role` (`client` | `admin`)
- `accepted_terms_at`, `terms_version` — consentimiento auditable de los
  términos. `has_accepted_current_terms` compara contra `settings.TERMS_VERSION`.
- `deactivated_at`, `deactivated_by` (FK a sí mismo, SET_NULL) — rastro de la
  deshabilitación. **No son un mecanismo de bloqueo**: el interruptor sigue
  siendo `is_active`. `deactivated_by` vacío = la deshabilitó el titular; con
  valor = la deshabilitó un admin y solo soporte puede reactivarla.
- `two_factor_enabled`, `two_factor_enabled_at` — el titular confirmó que tiene
  acceso a su correo. Obligatorio para poder deshabilitar la cuenta a uno mismo.
- `created_at`, `updated_at`

El login autentica por `username = email` (`LoginView` llama
`authenticate(username=email, ...)`). Cualquier usuario creado por admin, seed
o importación con `username` distinto de su email **no podrá iniciar sesión**.

En el mismo archivo, `TwoFactorCode` guarda los códigos de un solo uso
(`purpose`: `enable` | `deactivate` | `reactivate`), con `code_hash` hasheado,
`expires_at`, `used_at` y `failed_attempts`. `is_usable` resume si todavía
sirve; el admin solo los consulta.

## Rutas web

| Ruta | Nombre | Acceso |
|---|---|---|
| `/` | `core:home` | público |
| `/privacidad/` | `core:privacy` | público |
| `/catalogo/` | `catalog:home` | público |
| `/catalogo/<slug>/` | `catalog:product_detail` | público (compra solo con sesión) |
| `/carrito/` | `cart:cart` | con sesión |
| `/pedidos/checkout/` | `orders:checkout` | con sesión + carrito con items |
| `/pedidos/` | `orders:order_list` | con sesión |
| `/dashboard/` | `core:dashboard` | staff |
| `/admin/` | Django admin | staff |
| `/accounts/*` | login, registro, perfil, direcciones, desactivar cuenta | según caso |
| `/accounts/cuenta-pausada/` | `users:account_paused` | con la sesión que dejó el login |
| `/accounts/reactivar-cuenta/<token>/` | `users:account_reactivate` | público (enlace firmado) |
| `/accounts/verificacion-dos-pasos/` | `users:two_factor_setup` | cliente (los admin al panel) |

Todas en español, con barra final incluida. Nombres de URL con dos puntos para
los namespaces de app: `reverse('users:login')`.

## API REST

Montada en `/api/v1/`. 12 ViewSets registrados en `config/api_router.py`, con
prefijos en español:

```
catalogo/productos      catalogo/categorias
usuarios                direcciones
geo/departamentos       geo/municipios
inventario/movimientos  carrito/carritos   carrito/items
pedidos/pedidos         pedidos/items      pagos
```

- **Autenticación**: Session, Basic y JWT.
- **JWT**: `/api/v1/auth/token/` y `/api/v1/auth/token/refresh/`.
- **Esquema**: `/api/v1/schema/`, Swagger en `/api/v1/swagger/`, ReDoc en
  `/api/v1/redoc/`.
- **Permiso por defecto**: `IsAuthenticatedOrReadOnly`.

### Permisos propios

Todos en `apps/core/permissions.py`. La función `is_admin(user)` considera
admin a quien tenga `is_staff`, `is_superuser` **o** `role == 'admin'`.

| Clase | Permite |
|---|---|
| `IsAdminOrReadOnly` | lectura a todos, escritura a admin |
| `IsAuthenticatedOrAdminReadOnly` | lectura a autenticados, escritura a admin |
| `IsAdminOnly` | solo admin |
| `IsAdmin` | alias de solo admin |
| `IsAuthenticatedOwnedOrAdmin` | dueño del objeto o admin (sigue `obj.user`, o `obj.cart.user`) |

**Usa siempre estas clases en vez de escribir permisos ad hoc en cada ViewSet.**

## Páginas de error

`templates/errors/` contiene `base.html`, `404.html` y `403.html`. Son
**standalone**: no extienden `base.html`, porque una página de error debe
funcionar aunque la navbar o el footer fallen. `base.html` de errores carga solo
`core/css/errors.css`.

Los shims `templates/404.html` y `templates/403.html` extienden las anteriores
porque es el nombre fijo que Django busca en la raíz del proyecto.

Vistas de previsualización: `core:error_404` y `core:error_403` en `/errores/404/`
y `/errores/403/`.

`apps/core/middleware.py` (`CarelyErrorPagesMiddleware`) es el primero de
`MIDDLEWARE` y sirve esas páginas también con `DEBUG=True`, cuando Django
ignora los templates de error. Ver el gotcha en `GOTCHAS.md`. **No toca 500** ni
las rutas de `EXENT_PATHS` (`/api/`, `/static/`, `/media/`).

## Capas de templates

`templates/base.html` define los bloques:

`title`, `meta_description`, `extra_css`, `body_class`, `messages`, `content`,
`extra_js`.

- Plantillas de tienda extienden `base.html`.
- Las del panel extienden `apps/core/templates/core/dashboard_base.html`.
- Parciales compartidos: `navbar.html`, `footer.html`, `messages.html`.
- Componentes: `templates/components/`.

## Estáticos

- Globales en `static/`: `css/{variables,base,layout,theme,animations}.css`,
  `js/{main,navbar,alerts}.js`.
- Por app en `apps/<app>/static/<app>/`, que es la forma recomendada en Django
  porque evita colisiones de nombres.
- Cachebuster `?v=N` en el `<link>`. **Si editas un CSS que ya se sirve con
  `?v=N`, sube el número** o los navegadores con caché te mostrarán la versión
  vieja.

## Configuración por entorno

Se elige con la variable `DJANGO_ENV`, nunca con `DJANGO_SETTINGS_MODULE`:

```
DJANGO_ENV=development  →  config.settings.development   DEBUG=True, ALLOWED_HOSTS=['*']
DJANGO_ENV=test         →  config.settings.test          SQLite, migraciones OFF, hashers MD5
DJANGO_ENV=production   →  config.settings.production   DEBUG=False, SSL/HSTS, SECRET_KEY obligatorio
```

`manage.py`, `wsgi.py` y `asgi.py` leen `DJANGO_ENV` con fallback a
`development`.

El desarrollo y la producción usan **MySQL**, así que sin `.env` con credenciales
`runserver` falla al conectar. Los tests no.

## Context processors

En `apps/core/context_processors.py`, activos en todas las páginas:

- `site_settings` → `site_name`, `site_description`, `carely_email`,
  `carely_phone`, `carely_phone_href`, `carely_address`, `carely_socials`.
  Inyecta un **queryset sin evaluate** en cada página, pero devuelve un
  `QuerySet` perezoso, no una lista: no se ejecuta hasta que el template itera.
- `footer_categories` → `categories`, queryset de `Category.objects.filter(is_active=True)`.
- `cart_count` → suma de `quantity` de los items del carrito, con `try/except`
  para que un fallo de BD no rompa la página.

## Servicios con efectos secundarios

- `GmailService` y `GmailServiceError` viven en **`apps/users/services.py`**
  (`apps/core/services.py` está vacío). Envía correos de registro,
  recuperación de contraseña, deshabilitación de cuenta y confirmación de
  pedido. Lanza `GmailServiceError` si falla la red. **Las vistas lo capturan**
  y el flujo continúa: el fallo de email no debe tumbar un checkout. Mantén ese
  comportamiento.
- `disable_account`, `enable_account` y `notify_deactivation` (mismo archivo)
  son el camino único para cambiar el estado de una cuenta. Las tres rutas que
  la deshabilitan (perfil, toggle del panel, edición de usuario) llaman a
  `disable_account` + `notify_deactivation`; ninguna escribe `is_active` a mano.
- La reactivación tiene dos caminos, ambos solo si la cuenta la deshabilitó el
  titular:
  - Enlace firmado: `build_reactivation_token` / `resolve_reactivation_token`
    (`django.core.signing`), con vigencia `settings.ACCOUNT_REACTIVATION_TIMEOUT`.
    Llega por correo al deshabilitar la cuenta.
  - Código de un solo uso: `send_two_factor_code` / `consume_two_factor_code`
    en la pantalla de cuenta pausada (`purpose='reactivate'`).
- Verificación en dos pasos (`/accounts/verificacion-dos-pasos/`): el código se
  guarda hasheado con `make_password` y se compara con `check_password`. Se pide
  para **activar/desactivar el 2FA**, **deshabilitar la cuenta** y **reactivarla**;
  nunca en cada login. Ajustes: `TWO_FACTOR_CODE_LENGTH`, `TWO_FACTOR_CODE_TTL`,
  `TWO_FACTOR_MAX_ATTEMPTS`. Pedir uno nuevo borra los pendientes del mismo
  `purpose`. `DeactivateAccountForm` declara `code` al final a propósito: así el
  código no se consume si la contraseña o la confirmación fallan.
- El campo `code` se pinta con el parcial `users/_code_input.html`: una casilla
  por dígito (`code_digits`, que las vistas pasan como
  `range(settings.TWO_FACTOR_CODE_LENGTH)`). **El input real sigue siendo el que
  envía el formulario**, solo queda transparente; `users/js/code_input.js` lo
  replica en las casillas y maneja el salto de foco, el borrado y el pegado.
  Enlaza `users/css/code_input.css` **después** de `profile.css` / `auth.css`,
  porque gana por orden y no por especificidad.
- `cargar_colombia` es un management command (`apps/users/management/commands/`)
  que puebla `Department` y `City`.
