# Despliegue

## Vercel (recomendado)

Vercel detecta Django por `manage.py` en la raíz y resuelve el entrypoint desde
`WSGI_APPLICATION` (`config/wsgi.py`). Ejecuta `collectstatic` solo. Los
archivos de soporte en la raíz son `requirements.txt` (lista plana de
dependencias; Vercel no parsea `-r requirements/...`), `.python-version` y
`.vercelignore`.

### 1. Preparar servicios (una vez)

**MariaDB Cloud (SkySQL)**

- El `.env` de desarrollo usa `DJANGO_DB_HOST=localhost`; Vercel no puede
  alcanzar `localhost`, así que hacen falta las credenciales de la instancia
  en la nube (host público, usuario, contraseña). Instancia real del proyecto:
  `serverless-us-east4.sysp0000.db2.skysql.com:4001` (MariaDB 11.8.6), base
  `carely_prod`.
- La base debe existir ya: el proveedor normalmente no concede
  `CREATE DATABASE`. Puede ser una nueva (p. ej. `carely_prod`) o la misma
  que ya está en la nube.
- El firewall/allowlist del proveedor debe aceptar conexiones desde Internet
  (los builds y las funciones de Vercel salen de rangos de IP de AWS).

**Supabase Storage**: las 4 variables `SUPABASE_*` del `.env` apuntan al
bucket con las imágenes (producción y desarrollo usan `carely-images`; el
bucket `carely-prod` quedó vacío y se descartó); se copian tal cual
(incluido el sufijo `/rest/v1` de `SUPABASE_URL`, es correcto: `base.py`
usa solo el host). El bucket debe estar marcado como **público** en
Storage → Buckets, o las URLs `/storage/v1/object/public/...` devuelven
401/400.

**Gmail SMTP**: `.env` ya trae host, puerto, usuario y contraseña de
aplicación; se copian tal cual.

**Wompi**: el proyecto está en ambiente sandbox (`pub_test_`/`prv_test_`/
`test_integrity_`/`test_events_`) con `PAYMENT_GATEWAY=wompi` y
`WOMPI_API_URL=https://sandbox.wompi.co/v1`. Para pasar a real hay que
cambiar las 4 llaves a `pub_prod_`/`prv_prod_`/`prod_integrity_`/
`prod_events_` y `WOMPI_API_URL=https://production.wompi.co/v1`.

**`.env` como fuente de verdad**: los valores definitivos se completan en
`.env` (que nunca se commitea) y de ahí se copian al dashboard de Vercel.

### 2. Commitear y pushear los archivos de soporte

Vercel solo ve lo que está en GitHub, así que primero:

```powershell
.\Agent\verify.ps1
git add requirements.txt .python-version .vercelignore docs/deployment.md
git commit -m "Agregar archivos de soporte para despliegue en Vercel"
git push
```

### 3. Importar el repo

1. Entrar en <https://vercel.com/new> e iniciar sesión con GitHub.
2. **Import Git Repository** → seleccionar `AndresAkm/Carely`.
3. Framework: Vercel detecta Django automáticamente por `manage.py`. No tocar
   el entrypoint ni el Root Directory (`./`).
4. Aún no desplegar: primero las variables de entorno.

### 4. Variables de entorno (antes del primer deploy)

En **Settings → Environment Variables** (o en el paso equivalente del
asistente de importación). Production settings lanza `ImproperlyConfigured`
si faltan `DJANGO_SECRET_KEY` y `DJANGO_ALLOWED_HOSTS`, así que el build
falla a propósito si no están. Marcar cada variable para **Production**
(and Preview si se quieren deploys de PR).

| Variable | Valor |
|---|---|
| `DJANGO_ENV` | `production` (sin esto, `manage.py`/`wsgi.py` caen en development con DEBUG=True) |
| `DJANGO_SECRET_KEY` | secreto nuevo de Vercel; generar con `secrets.token_urlsafe(50)` en un REPL de Python |
| `DJANGO_ALLOWED_HOSTS` | `carely-nine.vercel.app,carely-hlwksimbn-jaym3gd2431-4137s-projects.vercel.app` (ambos dominios de Vercel; sin `https://`) |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://carely-nine.vercel.app,https://carely-hlwksimbn-jaym3gd2431-4137s-projects.vercel.app` (sin ellas, login y admin devuelven 403 en POST) |
| `DJANGO_DB_NAME` | `carely_prod` |
| `DJANGO_DB_HOST` | host público de MariaDB Cloud (nunca `localhost`) |
| `DJANGO_DB_USER` / `DJANGO_DB_PASSWORD` | credenciales de MariaDB Cloud |
| `DJANGO_DB_PORT` | `4001` (SkySQL; `3306` en el default de otros proveedores) |
| `SUPABASE_URL` / `SUPABASE_S3_ACCESS_KEY_ID` / `SUPABASE_S3_SECRET_ACCESS_KEY` / `SUPABASE_STORAGE_BUCKET` | igual que en `.env` (`SUPABASE_STORAGE_BUCKET=carely-images`), copiar y pegar |
| `DJANGO_EMAIL_BACKEND` | `django.core.mail.backends.smtp.EmailBackend` |
| `EMAIL_HOST` / `EMAIL_PORT` / `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` / `EMAIL_USE_TLS` / `DEFAULT_FROM_EMAIL` | igual que en `.env` |
| `WOMPI_PUBLIC_KEY` / `WOMPI_PRIVATE_KEY` / `WOMPI_INTEGRITY_SECRET` / `WOMPI_EVENTS_SECRET` / `WOMPI_API_URL` / `WOMPI_CHECKOUT_URL` | igual que en `.env` (sandbox: `pub_test_`/`prv_test_`/`test_integrity_`/`test_events_`, `https://sandbox.wompi.co/v1`) |
| `PAYMENT_GATEWAY` | `wompi` (sandbox actualmente; cambiar llaves para producción) |
| `CARELY_*` | opcionales (hay defaults en `base.py`) |

Nota: `.env` no se sube a GitHub (está en `.gitignore`), por eso hay que
copiar cada valor a mano al dashboard.

### 5. Build Command

**Settings → Build & Development Settings → Build Command**:

```
python manage.py migrate --noinput
```

`collectstatic` lo ejecuta Vercel solo; no incluirlo. La versión de Python
sale de `.python-version` (3.14).

### 6. Deploy

1. **Deployments → Deploy** (o reconectar el repo).
2. Leer el log del build. Debe mostrar: dependencias → migrate →
   collectstatic. Si falla:
   - `ImproperlyConfigured: DJANGO_SECRET_KEY must be defined` → falta la
     variable o no está marcada para Production.
   - `ImproperlyConfigured: DJANGO_ALLOWED_HOSTS ...` → ídem.
   - `Can't connect to MySQL server` / `Access denied` → host o credenciales
     de MariaDB Cloud; verificar que no sea `localhost` y que el firewall
     acepte conexiones externas.
   - El build tarda y falla en migrate → la BD no es alcanzable desde
     Vercel.

### 7. Post-despliegue

Correr desde local contra la BD en la nube (los valores del shell ganan
sobre los del `.env`):

```powershell
$env:DJANGO_ENV='production'
$env:DJANGO_DB_HOST='serverless-us-east4.sysp0000.db2.skysql.com'
$env:DJANGO_DB_USER='<usuario>'
$env:DJANGO_DB_PASSWORD='<contraseña>'
$env:DJANGO_DB_NAME='carely_prod'
$env:DJANGO_DB_PORT='4001'
$env:DJANGO_ALLOWED_HOSTS='localhost'
$env:DJANGO_CSRF_TRUSTED_ORIGINS='http://localhost:8000'
# DJANGO_SECRET_KEY lo aporta el .env local.

# Superusuario. username DEBE ser el email: el login autentica con
# username=email y con otro valor no se podría entrar al admin.
$env:DJANGO_SUPERUSER_USERNAME='admin@correo.com'
$env:DJANGO_SUPERUSER_EMAIL='admin@correo.com'
$env:DJANGO_SUPERUSER_PASSWORD='<contraseña>'
.\env\Scripts\python.exe manage.py createsuperuser --noinput

# Datos geográficos (Departamento/City), solo si la BD está vacía:
.\env\Scripts\python.exe manage.py cargar_colombia

# Catálogo real (6 categorías y 17 productos con imagen y precio en COP).
# La migración 0002_seed_data solo deja productos genéricos sin imagen;
# este comando los reemplaza y es idempotente (se puede volver a correr).
.\env\Scripts\python.exe manage.py cargar_catalogo
```

`cargar_catalogo` borra los productos genéricos de la semilla, salvo los que
tienen historial de pedidos o movimientos de inventario: esos quedan
desactivados (`is_active=False`, `stock=0`) y arrastran a sus categorías
(Maquillaje/Fragancias), que también se desactivan en vez de borrarse. Las
imágenes no se suben desde el comando: ya viven en el bucket
`carely-images` y solo se guarda su ruta en el campo `image`.

Pasos restantes:

1. Webhook de Wompi (ya configurado con `PAYMENT_GATEWAY=wompi`):
   `https://carely-nine.vercel.app/pagos/webhook/wompi/`, evento
   `transaction.updated`. Se registra en el dashboard de comercios de Wompi:
   **Developers → Seguimiento de transacciones → "URL de eventos"** (hay una
   por ambiente; configurar la de sandbox). El endpoint responde 400
   "Firma inválida." si el checksum no coincide con `WOMPI_EVENTS_SECRET`.
2. Smoke test: `/`, `/catalogo/`, `/admin/` (login completo),
   `/api/v1/swagger/`, estáticos, checkout en sandbox de Wompi, correo de
   registro.
3. Dominio custom: mantener actualizados `DJANGO_ALLOWED_HOSTS` y
   `DJANGO_CSRF_TRUSTED_ORIGINS` con todos los dominios que responde Vercel.

### Gotchas de este proyecto en Vercel

- Sin `DJANGO_ENV=production` el sitio arranca en development (DEBUG=True).
- Sin `DJANGO_CSRF_TRUSTED_ORIGINS` los POST (login, admin, checkout) dan 403.
- El filesystem es solo lectura: sin las 4 `SUPABASE_*`, las imágenes de
  `catalog` no se pueden subir.
- `gunicorn` y `psycopg` viven en `requirements.txt` (necesarios para el
  servidor tradicional; en Vercel se instalan pero no se usan como servidor).

## Requisitos (servidor tradicional)

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
