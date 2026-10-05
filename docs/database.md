# Base de datos

## Desarrollo

- Motor principal: MariaDB Cloud mediante el backend MySQL de Django.
- Base: `carely`.
- Configuración: `config/settings/development.py` hereda de `base.py`.
- Las credenciales y el host se proporcionan mediante variables `DJANGO_DB_*`.
- `db.sqlite3` se conserva como respaldo y ya no es la base principal.
- El seed de categorías y productos se carga con una migración de datos:
  `apps/catalog/migrations/0002_seed_data.py`.

### Migraciones

```powershell
env\Scripts\python.exe manage.py makemigrations
env\Scripts\python.exe manage.py migrate
```

### Superusuario

```powershell
env\Scripts\python.exe manage.py createsuperuser
```

## Producción

- Motor: MariaDB Cloud mediante `django.db.backends.mysql`.
- Base: `carely` (configurable vía variables de entorno en `.env`).
- Variables usadas por `config/settings/production.py`:

El motor es fijo (`django.db.backends.mysql`) y se define en
`config/settings/base.py`; no hay variable de entorno para cambiarlo.

| Variable | Valor por defecto |
|----------|-------------------|
| `DJANGO_DB_NAME` | `carely` |
| `DJANGO_DB_USER` | *(vacío)* |
| `DJANGO_DB_PASSWORD` | *(vacío)* |
| `DJANGO_DB_HOST` | *(vacío)* |
| `DJANGO_DB_PORT` | `3306` |

En los tests (`config/settings/test.py`) se usa SQLite sobre `db_test.sqlite3`,
porque MariaDB Cloud no concede `CREATE DATABASE`.

## Supabase Storage

Las imágenes de categorías y productos utilizan un bucket público de Supabase
mediante el backend S3-compatible de `django-storages`. El bucket debe existir
previamente y su nombre se configura con `SUPABASE_STORAGE_BUCKET`.

Variables necesarias:

```text
SUPABASE_URL
SUPABASE_S3_ACCESS_KEY_ID
SUPABASE_S3_SECRET_ACCESS_KEY
SUPABASE_STORAGE_BUCKET
```

Las credenciales S3 se utilizan únicamente en el backend. No se exponen en
templates, JavaScript ni respuestas API. Las rutas conservan los prefijos
`categories/` y `products/`.

## Modelos

| App | Modelos |
|-----|---------|
| `apps.catalog` | `Category`, `Product` |
| `apps.core` | *(sin modelos)* |
| `apps.users` | `User`, `Department`, `City`, `Address`, `TwoFactorCode` |
| `apps.inventory` | `InventoryMovement` |
| `apps.cart` | `Cart`, `CartItem` |
| `apps.orders` | `Coupon`, `Order`, `OrderItem`, `OrderStatusHistory` |
| `apps.payments` | `Payment` |

### Relaciones principales

- `User` ← `Cart`, `Order`, `Address`, `InventoryMovement`, `TwoFactorCode`.
- `Department` ← `City` ← `Address`.
- `Category` ← `Product` ← `CartItem`, `OrderItem`, `InventoryMovement`.
- `Cart` ← `CartItem` (único por `cart` + `product`).
- `Order` ← `OrderItem`, `OrderStatusHistory`, `Payment` (PROTECT), `Coupon` (SET_NULL).
- `Address` usa borrado lógico (`is_active`); `City` y `Department` están en PROTECT.
- `User.is_active` es el único interruptor de una cuenta. `deactivated_at` y
  `deactivated_by` (SET_NULL a `self`) son solo rastro: `deactivated_by` vacío
  significa que la deshabilitó el titular, y con valor que la deshabilitó un
  administrador. El enlace de reactivación solo sirve en el primer caso.
- `TwoFactorCode` guarda códigos de un solo uso con `purpose` (`enable`,
  `deactivate`, `reactivate`). `code_hash` nunca está en claro: se compara con
  `django.contrib.auth.hashers.check_password`. Pedir uno nuevo borra los
  pendientes del mismo uso, así que hay como máximo uno vigente. Los códigos se
  pueden auditar en el admin, pero no se crean ni se editan a mano.
