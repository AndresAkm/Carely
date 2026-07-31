# Despliegue

## Requisitos

- Python 3.12+
- PostgreSQL (producción)
- `config/settings.production` como `DJANGO_SETTINGS_MODULE`

## Pasos

1. Instalar dependencias:

   ```bash
   pip install -r requirements/production.txt
   ```

2. Configurar variables de entorno (copiar `.env.example` a `.env`):

   - `DJANGO_SECRET_KEY`: secreto seguro y único.
   - `DJANGO_ALLOWED_HOSTS`: dominios separados por coma.
   - `DJANGO_DB_*`: credenciales de PostgreSQL.

3. Aplicar migraciones y recolectar estáticos:

   ```bash
   python manage.py migrate --settings=config.settings.production
   python manage.py collectstatic --settings=config.settings.production
   ```

4. Servir con WSGI (`config/wsgi.py`) mediante Gunicorn/uWSGI y un proxy como Nginx.
   - Nginx sirve `staticfiles/` y `media/`.

## Variables de entorno

| Variable | Obligatoria | Descripción |
|----------|-------------|-------------|
| `DJANGO_SECRET_KEY` | Sí | Secreto de Django |
| `DJANGO_ALLOWED_HOSTS` | Sí | Hosts permitidos |
| `DJANGO_DB_*` | No | Credenciales de BD (defaults aplicables) |
