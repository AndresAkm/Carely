# Base de datos

## Desarrollo

- Motor: SQLite (archivo `db.sqlite3` en la raíz del proyecto).
- Configuración: `config/settings/development.py` hereda de `base.py`.
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

- Motor por defecto: PostgreSQL (configurable vía variables de entorno en `.env`).
- Variables usadas por `config/settings/production.py`:

| Variable | Valor por defecto |
|----------|-------------------|
| `DJANGO_DB_ENGINE` | `django.db.backends.postgresql` |
| `DJANGO_DB_NAME` | `carely` |
| `DJANGO_DB_USER` | `carely` |
| `DJANGO_DB_PASSWORD` | *(vacío)* |
| `DJANGO_DB_HOST` | `localhost` |
| `DJANGO_DB_PORT` | `5432` |

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
