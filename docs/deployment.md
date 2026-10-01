# Despliegue

## Requisitos

- Python 3.12+
- MariaDB / MySQL (producción)
- `config/settings.production` como `DJANGO_SETTINGS_MODULE`

## Pasos

1. Instalar dependencias:

   ```bash
   pip install -r requirements/production.txt
   ```

2. Configurar variables de entorno (copiar `.env.example` a `.env`):

   - `DJANGO_SECRET_KEY`: secreto seguro y único.
   - `DJANGO_ALLOWED_HOSTS`: dominios separados por coma.
   - `DJANGO_DB_*`: credenciales de MariaDB/MySQL.
   - `SUPABASE_*`: bucket S3-compatible para imágenes.
   - `EMAIL_*`: SMTP de Gmail.
   - `CARELY_*`: datos públicos de la tienda (nombre, email, teléfono, redes).

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
| `DJANGO_DB_NAME` | Sí | Nombre de la base |
| `DJANGO_DB_USER` | Sí | Usuario de la BD |
| `DJANGO_DB_PASSWORD` | Sí | Contraseña de la BD |
| `DJANGO_DB_HOST` | Sí | Host de MariaDB |
| `DJANGO_DB_PORT` | No | Puerto (por defecto `3306`) |
| `SUPABASE_STORAGE_BUCKET` | Sí | Bucket de imágenes |
| `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | Sí | Credenciales SMTP |
| `CARELY_*` | No | Datos públicos de la tienda (hay defaults) |
