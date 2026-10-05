# Convenciones

Cómo se ve el código aquí. Copia la convención existente en lugar de inventar
una nueva.

## Globales

- **Español** en toda la UI: textos, `verbose_name`, `help_text`,
  `error_messages`, mensajes de `messages`, nombres de permisos del API.
- Sangría de 4 espacios. Sin tabs.
- Comillas simples en Python.
- Los imports siguen el orden de `isort`: stdlib, terceros, proyecto.
  Actualmente no
  hay linter que lo imponga, así que mantenlo a mano.
- Sin `print()`. Para depurar temporalmente, quita la línea antes de terminar.
- Sin comentarios que explique *qué* hace el código; sí comentarios que
  explican *por qué* una decisión es rara. El código ya dice qué hace.

## Modelos

```python
class Category(models.Model):
    name = models.CharField('nombre', max_length=100)
    slug = models.SlugField('slug', unique=True, blank=True)

    class Meta:
        verbose_name = 'categoría'
        verbose_name_plural = 'categorías'
        ordering = ['name']

    def __str__(self):
        return self.name
```

Obligatorio:

- **`verbose_name` en todos los campos.** Sin excepción.
- **`related_name` en cada `ForeignKey`.** Si no lo pones, Django crea un
  inverso con el nombre del modelo y luego choca.
- **`class Meta`** con `verbose_name` y `ordering`. El `ordering` es lo que
  decide el orden por defecto de listados y APIs; sin él el orden es indefinido.
- **`__str__`** que devuelva algo legible. Para `User` es `self.email`.
- Sin `db_table`. El proyecto no lo usa.

Para timestamps, copia el patrón existente:

```python
created_at = models.DateTimeField(auto_now_add=True, verbose_name='creado en')
updated_at = models.DateTimeField(auto_now=True, verbose_name='actualizado en')
```

## Formularios

`ModelForm` cuando el modelo existe; `Form` plano cuando el formulario no
guarda nada (`LoginForm`, `DeactivateAccountForm`, `ForceDeleteUserForm`).

- Widgets con `class` de Bootstrap: `form-control`, `form-check-input`,
  `form-select`.
- Placeholders en español y `autocomplete` correcto (`email`, `new-password`,
  `current-password`, `tel`).
- `error_messages` en español cuando el mensaje por defecto no sirve:

```python
confirm = forms.BooleanField(
    label='Entiendo que mi cuenta quedará deshabilitada',
    error_messages={'required': 'Debes confirmar que entiendes las consecuencias.'},
    widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
)
```

- `clean_<campo>()` para validación de un campo; `clean()` para la que cruza
  varios.
- Si el formulario tiene una dependencia de otro campo (los selects encadenados
  de Colombia), extrae un mixin: `_ColombiaAddressMixin` en
  `apps/users/forms.py` es el ejemplo a seguir.

## Vistas web

Dos estilos conviven; usa el de la app:

- `apps/cart/views/web.py` usa **FBV** porque las acciones son POST directos
  (`cart_add`, `cart_update`, `cart_remove`).
- El resto usa **CBV**: `LoginRequiredMixin` de Django, y para el panel
  `UserPassesTestMixin` con los mixins de `apps/*/views/dashboard.py`.

```python
class AccountDeactivateView(LoginRequiredMixin, FormView):
    template_name = 'users/deactivate_account.html'
    form_class = DeactivateAccountForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
```

## API

- ViewSet + `DefaultRouter`, registrado en `config/api_router.py` con prefijo en
  español y `basename` explícito.
- Permisos de `apps/core/permissions.py`, nunca lógica ad hoc en el ViewSet.
- `perform_destroy()` para el borrado lógico de `Address`.
- Filtra el queryset por propietario en `get_queryset()`. `IsAuthenticatedOwnedOrAdmin`
  ya cubre el `has_object_permission`, pero el queryset no filtra solo.
- Si añades campos al modelo exposed por la API, actualiza el serializer, el
  `list_display` del admin y `docs/api.md`.

## Templates

- Extiende `base.html` (tienda) o `core/dashboard_base.html` (panel).
- CSS en `{% block extra_css %}`, JS en `{% block extra_js %}`.
- **Sin `<style>` ni `<script>` inline.** El CSS va en un archivo estático de la
  app. La única excepción aceptada son los correos HTML, donde no hay contexto
  de estáticos.
- Al enlazar un CSS, versiona: `{% static 'users/css/auth.css' %}?v=3`. **Sube el
  número cuando cambies el archivo**, si no el navegador sirve la versión vieja.
- Nombra los inputs para que el JS del proyecto los encuentre. Por ejemplo, el
  JavaScript del timeline de pedidos busca `id_order_notes`, y ese `id` lo define
  el widget del formulario. Si renombras el campo, rompe el JS en silencio.
- Si añades un campo a un formulario, renderiza también sus errores; el
  proyecto lo hace campo por campo.

## CSS

- Clases de Bootstrap para estructura y espaciado; CSS propio para componente.
- Variables de `static/css/variables.css` (`--clr-primary`, `--clr-text`,
  `--clr-border`, `--clr-bg`, …). No pongas colores hex sueltos si ya existe
  una variable.
- Para el color de error, el patrón ya establecido en el repo es
  `var(--clr-danger, #dc3545)`.
- `rem` para tipografía, `em` no se usa.

## Tests

- Una clase por comportamiento, nombrada `AlgoTests` (no `TestAlgo`).
- Métodos `test_<comportamiento_en_español_o_inglés>`, descriptivos.
- Web: `TestCase` de `django.test` y `reverse()` siempre, nunca URLs escritas a mano.
- API: `APITestCase` de `rest_framework.test`.
- Concurrencia: `TransactionTestCase` (ver `apps/inventory/tests.py`).
- Helpers de creación al principio del archivo:

```python
def create_user(**kwargs):
    defaults = {
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'pass12345',
    }
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)
```

- **Si cambias un test existente, es que el comportamiento cambió a propósito.**
  Si no es así, no lo toques para hacerlo pasar.
- No hay factories ni fixtures. Sigue el patrón de helpers.
- Contexto de error: los tests de email y red usan mocks y capturan
  `GmailServiceError`. La suite imprime un error de red esperado en su salida,
  y aun así termina en `OK`; no lo confundas con un fallo.

## Admin

- `list_display`, `list_filter`, `search_fields` con `ordering`.
- Los campos propios van en un `fieldsets` extra con etiqueta en español
  (`CarelyUserAdmin` agrupa "Información adicional" y "Términos y condiciones").
- `UserAdmin.has_delete_permission` devuelve `False` a propósito: el borrado de
  usuarios está centralizado en el flujo de borrado forzado del panel.

## Settings

- Variable de entorno con valor por defecto en `config/settings/base.py`.
- Documenta la variable en `.env.example` **en el mismo cambio**.
- Los datos públicos y de contacto usan el prefijo `CARELY_`.
- Si añades un setting que afecte a la UI, expónlo por `site_settings` para no
  hardcodearlo en el template.
