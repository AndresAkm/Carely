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

| Variable | Valor por defecto |
|----------|-------------------|
| `DJANGO_DB_ENGINE` | `django.db.backends.mysql` |
| `DJANGO_DB_NAME` | `carely` |
| `DJANGO_DB_USER` | `carely` |
| `DJANGO_DB_PASSWORD` | *(vacío)* |
| `DJANGO_DB_HOST` | `localhost` |
| `DJANGO_DB_PORT` | `3306` |

## Modelos

| App | Modelos |
|-----|---------|
| `apps.catalog` | `Category`, `Product` |
| `apps.core` | *(sin modelos)* |
| `apps.users` | `User` |
| `apps.inventory` | `InventoryMovement` |
| `apps.cart` | `Cart`, `CartItem` |
| `apps.orders` | `Order`, `OrderItem` |
| `apps.payments` | `Payment` |
