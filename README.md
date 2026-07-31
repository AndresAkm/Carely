# Carely

Tienda de cuidado personal construida con Django 6. Proyecto educativo estructurado en capas (`config`, `apps`, `templates`, `static`, `media`, `requirements`, `docs`).

## Estructura

```
Carely_Django/
├── config/                # Configuración del proyecto (settings por entorno)
│   └── settings/          # base, development, production
├── apps/
│   ├── core/              # Página de inicio y dashboard (+ static/core/)
│   ├── catalog/           # Categorías y productos (+ static/catalog/)
│   ├── users/             # Login, registro y logout (+ static/users/)
│   ├── inventory/         # (por implementar)
│   ├── cart/              # (por implementar)
│   ├── orders/            # (por implementar)
│   └── payments/          # (por implementar)
├── templates/             # Templates compartidos
├── static/                # Recursos globales (css, js, icons, vendors)
│   ├── css/               # variables, base, layout, theme, animations
│   ├── js/                # main, navbar, alerts
│   └── vendors/           # bootstrap, fontawesome
├── media/                 # Archivos subidos por usuarios
├── requirements/          # base, development, production
└── docs/                  # api, database, deployment
```

Los recursos específicos de cada funcionalidad viven dentro de su app en
`apps/<app>/static/<app>/` (css, js e imágenes), siguiendo el namespace
recomendado por Django y conservando `static/` únicamente para lo compartido.


## Requisitos

- Python 3.12+
- Django 6.x (ver `requirements/base.txt`)

## Instalación (desarrollo)

```powershell
# Crear y activar el entorno virtual
python -m venv env
.\env\Scripts\Activate.ps1

# Instalar dependencias
pip install -r requirements\development.txt

# Copiar variables de entorno
Copy-Item .env.example .env

# Migraciones y seed (categorías y productos)
python manage.py makemigrations
python manage.py migrate

# Crear superusuario (opcional)
python manage.py createsuperuser

# Levantar el servidor
python manage.py runserver
```

## Rutas principales

- `/` — Página de inicio
- `/catalogo/` — Catálogo de productos
- `/accounts/login/` y `/accounts/register/` — Autenticación
- `/dashboard/` — Dashboard (solo staff)
- `/admin/` — Panel de administración

## Documentación

- API y rutas: `docs/api.md`
- Base de datos: `docs/database.md`
- Despliegue: `docs/deployment.md`
