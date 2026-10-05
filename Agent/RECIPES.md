# Recetas

Procedimientos paso a paso para las tareas que más se repiten. Cada receta
incluye los tests que debería tener el resultado.

Antes de empezar, recuerda: `$env:DJANGO_ENV='development'` para migraciones,
`'test'` para verificar. Nunca mezcles.

---

## 1. Añadir un campo a un modelo existente

```powershell
# 1. Edita apps/<app>/models.py — con verbose_name
# 2. Genera la migración (OJO: development, no test)
$env:DJANGO_ENV='development'; .\env\Scripts\python.exe manage.py makemigrations <app>
# 3. LEE el archivo generado antes de aplicarla
# 4. Aplica
$env:DJANGO_ENV='development'; .\env\Scripts\python.exe manage.py migrate
# 5. Si el campo aparece en formularios, actualiza Meta.fields y el widget
# 6. Si lo expone la API, serializer + list_display del admin + docs/api.md
```

Tests: el formulario nuevo, y el de la API si aplica.

**Cuidado**: los tests desactiva migraciones y crean las tablas desde los
modelos, así que un test **no** detecta una migración que falte. Para eso está
`makemigrations --check --dry-run`.

---

## 2. Crear un modelo nuevo

1. `models.py`, con `verbose_name`, `related_name`, `Meta` con `ordering` y
   `__str__`.
2. `makemigrations <app>` y revisa el archivo.
3. `admin.py` con `list_display`, `list_filter`, `search_fields`.
4. `serializer.py` si va a la API.
5. Tests de modelo.

Si es un modelo que se borra lógicamente, copia `Address`: campo `is_active`,
filtro en el queryset y `perform_destroy()` que lo desactiva en vez de borrar.

---

## 3. Añadir una página web

1. **Vista** en `apps/<app>/views/web.py` (FBV) o el archivo del módulo.
   Hereda `base.html`.
2. **URL** en `apps/<app>/urls.py` con `name` en español y barra final:

```python
app_name = '<app>'
urlpatterns = [
    path('ruta/', MiVista.as_view(), name='nombre_en_espanol'),
]
```

3. **Template** en `apps/<app>/templates/<app>/<nombre>.html`:

```django
{% extends 'base.html' %}
{% load static %}

{% block title %}Título - {{ site_name }}{% endblock %}
{% block extra_css %}<link href="{% static '<app>/css/<archivo>.css' %}?v=1" rel="stylesheet">{% endblock %}
{% block body_class %}...{% endblock %}

{% block content %}
{% endblock %}
```

4. **CSS** en `apps/<app>/static/<app>/css/`. Nunca `<style>` inline.
5. Tests con `reverse()`.

---

## 4. Añadir un endpoint a la API

1. **Serializer** en `apps/<app>/serializer.py`.
2. **ViewSet** en `apps/<app>/views/api.py`:

```python
class MiViewSet(viewsets.ModelViewSet):
    queryset = MiModelo.objects.all()
    serializer_class = MiSerializer
    permission_classes = [IsAuthenticatedOrAdminReadOnly]   # de apps.core.permissions
```

3. **Registro** en `config/api_router.py`:

```python
router.register('prefijo/en_espanol', MiViewSet, basename='en-espanol')
```

4. **Permisos**: usa las clases de `apps/core/permissions.py`. Si none encaja,
  probablemente encaja `IsAuthenticatedOwnedOrAdmin` (dueño o admin).
5. **Filtra el queryset** en `get_queryset()` por propietario.
6. **Tests** en la clase `AlgoAPITests` con `APITestCase`, cubriendo el caso
   positivo **y** el 403 de un usuario sin permisos.
7. Actualiza `docs/api.md`.

---

## 5. Añadir un formulario a una vista

1. Campo en `forms.py` con widget de Bootstrap y `autocomplete` correcto.
2. Añádelo a `Meta.fields` si es `ModelForm`.
3. Renderízalo **con sus errores** en el template.
4. Si el JS depende de su `id`, dale uno explícito en el widget
   (`attrs={'id': 'id_mi_campo'}`), como hace `notes` con `id_order_notes`.
5. Test: envío inválido produce el error; envío válido persiste.

---

## 6. Enviar un correo

1. Método en `apps/users/services.py`, junto a `GmailService`.
2. Lanza `GmailServiceError` si falla; **no** te tragues la excepción.
3. En la vista, envuélvelo:

```python
try:
    enviado = GmailService.send_algo(user, request)
except GmailServiceError:
    enviado = False
```

4. Los fallos de email **no** deben revertir la operación de negocio. El usuario
   queda registrado aunque el correo falle.
5. Test: mockea el servicio y comprueba que el flujo principal sobrevive.

---

## 7. Cambiar un ajuste de configuración

1. `config/settings/base.py` con `os.environ.get('CARELY_X', 'por_defecto')`.
2. Documéntalo en `.env.example` **en el mismo cambio**.
3. Si lo necesita un template, expónlo en `site_settings`
   (`apps/core/context_processors.py`) y usa la variable en el template.
4. No toques `config/settings/test.py`.

---

## 8. Añadir un ajuste de permisos

Al tocar `apps/core/permissions.py` recuerda: afecta a toda la API.

1. Modifica la clase.
2. Añade un test que demuestre que un usuario **sin** permiso recibe 403.
3. Ejecuta la suite completa: otras apps dependen de estos permisos.

---

## 9. Cambiar el CSS

1. Edita `apps/<app>/static/<app>/css/<archivo>.css`.
2. **Sube el `?v=N`** en el template que lo enlaza. Sin esto, el navegador
   sirve la versión cacheada y jurarás que el cambio no funciona.
3. Usa las variables de `static/css/variables.css` en vez de colores sueltos.

---

## 10. Eliminar código muerto

1. **Verifica que está muerto**: busca referencias en el código **y** en los
   templates. Un `.html` o un `urls.py` puede no estar incluido en ningún
   `urlpatterns`.
2. **Pregunta antes de borrar.** Borrar archivos es destructivo y no se deshace
   en el diff del mismo modo.
3. Comprueba con `manage.py check` y la suite completa.

Ejemplo real: `apps/*/urls_api.py` estaban muertos porque los ViewSets se
registran en `config/api_router.py`, no en un `include()` por app. Antes de
borrarlos, comprueba `config/urls.py`.
