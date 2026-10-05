# Trampas y errores conocidos

Cosas que ya están resueltas o documentadas para que no pierdas tiempo, y otros
puntos ciegos reales del repositorio.

---

## Trampas del entorno

### `python manage.py test` falla con "Access denied ... test_carely"

Estás usando los settings de `development`, que apuntan a MySQL, e intenta crear
la base `test_carely` en el servidor real. No tienes permiso.

```powershell
$env:DJANGO_ENV='test'   # esto usa SQLite y una base local
```

Los tests solo funcionan con `DJANGO_ENV=test`. Es el error más común al empezar.

### `ModuleNotFoundError: No module named 'django'`

Estás usando el Python global. El intérprete del proyecto es
`.\env\Scripts\python.exe`.

### `makemigrations` dice "migrations have been disabled"

`config/settings/test.py` define `MIGRATION_MODULES = DisableMigrations()`, que
hace que *toda* clave de app parezca tener migraciones. Para migrar usa
`DJANGO_ENV=development`.

Consecuencia importante: **un test no puede detectar que falta una migración**,
porque construye las tablas desde los modelos directamente. Si añades un campo y
el test pasa, sigue faltando la migración. Compruébalo aparte:

```powershell
$env:DJANGO_ENV='development'; .\env\Scripts\python.exe manage.py makemigrations --check --dry-run
```

### `runserver` no arranca

`development` usa **MySQL**. Sin `.env` con credenciales válidas, falla al
conectar. Copia `.env.example` a `.env` y ajústalo, o usa `DJANGO_ENV=test` para
probar páginas sin base de datos real.

### El estado de `DJANGO_ENV` persiste en la sesión de PowerShell

Si corriste `makemigrations` en development y luego `test` sin volver a poner la
variable, el comando siguiente usa el entorno equivocado. Fíjate siempre.

---

## El output que asusta pero no es un fallo

La suite imprime esto:

```
Error al enviar correo de confirmación
para el pedido #1: Fallo de red al enviar el correo
```

Es **esperado**: un test simula un fallo de red de Gmail para comprobar que el
pedido se confirma igual. La suite termina en `Ran 205 tests ... OK`. Si ves
`OK` al final, todo bien.

---

## Trampas del código

### Con `DEBUG=True` Django ignora `404.html` y `403.html`

Es la trampa más fácil de perder tiempo. En `django/core/handlers/exception.py`,
`response_for_exception()` hace esto:

```python
if isinstance(exc, Http404):
    if settings.DEBUG:
        response = debug.technical_404_response(request, exc)   # <- gana siempre
    else:
        response = get_exception_response(...)                  # <- usa 404.html
```

Con `DEBUG=True` Django **nunca** llega a leer `templates/404.html`, aunque
exista, y da igual que registres `handler404` en `urls.py`. Lo mismo con 403.

Por eso existe `apps/core/middleware.py`: intercepta las respuestas 403/404 ya
generadas y las vuelve a pintar con las plantillas de Carely. Si añades una
página de error, no esperes verla en `runserver` solo por crear el template.

Lo que el middleware **no** toca:

- **500**: la página técnica con traceback es justo lo útil en desarrollo.
- **`/api/`, `/static/`, `/media/`**: ver `EXENT_PATHS` en el middleware.
- **Clientes que no aceptan HTML**: si el `Accept` pide `application/json` y no
  `text/html`, la respuesta pasa intacta. Sin esto, DRF devolvería JSON y una
  vista de DRF con un `404` se convertiría en HTML, rompiendo al cliente.

### El login depende de que `username == email`

`LoginView` llama `authenticate(request, username=email, ...)`. El registro
guarda `username = email`, así que los usuarios de la web funcionan. Pero un
usuario creado por el **admin**, por un seed o por una importación con `username`
distinto **no podrá iniciar sesión nunca**.

Si creas usuarios por código, copia la convención de `RegisterForm.save()`:

```python
user.username = self.cleaned_data['email']
```

### El ID del campo de notas lo define el JavaScript, no el formulario

`apps/orders/templates/orders/dashboard/order_status_form.html` busca
`id_order_notes` para restaurar el valor al cancelar un cambio de estado. Ese
`id` lo pone el widget `forms.Textarea(attrs={'id': 'id_order_notes'})` en
`OrderStatusForm`.

Si renombras el campo o el widget sin actualizar el JS, el botón
"deshacer" deja de funcionar **sin ningún error visible**. Es un fallo silencioso.

### Los totales de pedido los recalcula una señal, no `save()`

`apps/orders/signals.py` recalcula `Order.total` en `post_save` y `post_delete`
de `OrderItem`. `Order.save()` tiene además lógica condicionada por
`update_fields` para no interferir con el checkout.

Si añades una forma más de modificar `OrderItem`, comprueba que no duplicas el
cálculo ni disparas recursión.

### `Address` se borra en lógica, no físicamente

`AddressViewSet.perform_destroy()` pone `is_active=False` y
`is_default=False`; el queryset filtra `is_active=True`. Un `Address.objects.all()`
te devuelve también las direcciones dadas de baja. Filtra explícitamente.

### `is_admin` no es lo mismo que `is_staff`

`is_admin(user)` en `apps/core/permissions.py` devuelve `True` si el usuario
tiene `is_staff` **o** `is_superuser` **o** `role == 'admin'`. Un usuario creado
con `role='admin'` por el panel es admin aunque no tenga `is_staff`.

### Los context processors tocan toda la web

`site_settings`, `footer_categories` y `cart_count` corren en cada petición. Son
la causa más común de que una página se caiga. Si añades uno nuevo:

- devuelve un QuerySet perezoso, no una lista;
- envuelve las consultas en `try/except` como hace `cart_count`;
- no lo registres dos veces en `settings.TEMPLATES`.

---

## Huecos reales del repositorio

No son trampas, son cosas que faltan. **Menciónalas, no las arregles de paso.**

### `catalog` no tiene `tests.py`

No existe el archivo. El detalle de producto se prueba desde
`apps/core/tests.py`. Si tocas catálogo, crea el archivo y mueve o duplica lo
que toque. **`catalog` tiene 0 tests propios.**

### `payments/tests.py` está vacío

0 bytes. La app de pagos no tiene ninguna cobertura.

### Archivos vacíos

Estos existen y están versionados, pero están vacíos:

```
apps/core/models.py       apps/core/admin.py       apps/core/services.py
apps/core/signals.py      apps/core/utils.py      apps/catalog/services.py
apps/payments/services.py apps/payments/views.py  apps/payments/tests.py
apps/users/signals.py     apps/inventory/views.py apps/orders/views.py
```

`services.py` vacíos son **placeholders deliberados**: la capa de servicios está
reservada pero sin usar. Si añades lógica de negocio a una app, `services.py` es
donde va. No los llames "código muerto" sin confirmar con el usuario.

### No hay linter, ni formateador, ni pre-commit

No existe `pyproject.toml`, `setup.cfg`, `tox.ini`, `.flake8` ni
`.pre-commit-config.yaml`. No asumas que `ruff`, `black` o `flake8` están
disponibles: no están instalados. **Tu revisión manual del diff es la única red.**

### `db.sqlite3` y `db_test.sqlite3` están versionados

Están en `.gitignore`, pero ya estaban en el índice de Git, así que `.gitignore`
no los protege. Si contienen datos reales, hay que sacarlos del seguimiento:

```powershell
git rm --cached db.sqlite3 db_test.sqlite3
```

Lo mismo con `staticfiles/` (133 archivos) y 7 `.pyc` sueltos bajo
`apps/core/__pycache__/`. **Pide confirmación antes de hacerlo**: son cambios de
índice que el usuario puede no querer.

### `psycopg` está en `production.txt` sin usarse

El proyecto usa **MySQL** vía PyMySQL. `psycopg` (driver de PostgreSQL) está
listado pero ningún motor de base de datos es PostgreSQL. Es residuo.

### `docs/` queda desactualizado con facilidad

`docs/api.md`, `docs/database.md` y `docs/deployment.md` están bien ahora, pero
se desincronizan solos. Si añades un endpoint o un campo, actualízalos en el
mismo cambio.

---

## Sobre las afirmaciones sobre este proyecto

Ha llegado un análisis que afirmaba que "no hay tests" y que "el archivo de tests
está vacío". **Era falso**: había 154 tests en 31 clases antes de tocar nada.

Si un análisis previo te dice que algo "no existe", **verifícalo antes de
actuar**. Es más barato que invertir en refactorizar código que sí está.
