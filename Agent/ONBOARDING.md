# Primera sesión

Para un agente que no conoce el proyecto. Sigue estos pasos en orden.

## 1. Orientación (10 min)

Lee, en este orden:

1. [`README.md`](README.md) — el mapa y las reglas de oro.
2. [`GOTCHAS.md`](GOTCHAS.md) — **esto primero**, te ahorra horas.
3. [`ARCHITECTURE.md`](ARCHITECTURE.md) — cómo encaja todo.

No hace falta leer `CONVENTIONS.md` ni `RECIPES.md` hasta que vayas a escribir
código; entonces son tu referencia.

## 2. Comprueba que el entorno funciona

```powershell
.\Agent\verify.ps1
```

Debe terminar en `Todo correcto.` Si no, arregla eso antes de tocar nada: sin
una base sana no sabrás si un fallo es tuyo.

Si da error de Django, no estás usando el venv:
`.\env\Scripts\python.exe manage.py check`.

## 3. Explora el código de tu tarea

```powershell
# ¿Dónde vive algo?
git grep -n "término que buscas" -- apps config templates

# ¿Qué rutas declara cada módulo?
git grep -n "path(" -- apps config
```

Lee el archivo **completo** antes de editarlo, y al menos uno de sus vecinos.
En este proyecto las convenciones se ven mejor en el código que en la
documentación.

## 4. Haz el cambio

Consulta [`RECIPES.md`](RECIPES.md) para el tipo de tarea. Si no está, sigue
el patrón del archivo más parecido que ya exista.

## 5. Verifica

```powershell
.\Agent\verify.ps1
git diff
```

Lee el diff entero. No te saltes este paso: no hay linter, así que nada más va
a detectar un error de sintaxis visual o un resto de depuración.

---

## Preguntas frecuentes

**¿Dónde pongo una cosa nueva?**
En la app a la que pertenece. Si no sabes cuál, es `core`.

**¿Cómo añado un campo a un modelo que ya tiene admin y API?**
Ver [`RECIPES.md` §1](RECIPES.md). Los cinco sitios que se actualizan juntos son
el modelo, la migración, el serializer, el admin y `docs/api.md`.

**¿Por qué `makemigrations` falla con "migrations have been disabled"?**
Porque estás en `DJANGO_ENV=test`. Usa `development`.

**¿Cómo veo todas las rutas del proyecto?**
No hay `django-extensions` instalado, así que `manage.py show_urls` no existe.
Usa `git grep "path(" -- apps config`.

**¿Por qué los tests dicen `Access denied for user 'carely_app'`?**
Estás en `development` (MySQL). Usa `DJANGO_ENV=test`.

**Ese error de "Fallo de red al enviar el correo" en la salida de los tests, ¿es un fallo?**
No. Es un test que simula una caída de red. Si la línea final dice `OK`, todo
está bien.

**¿Puedo commitear?**
Solo si te lo piden. No stages ni commitees por iniciativa propia.

**Encontré código muerto. ¿Lo borro?**
Verifica que está muerto y **pregunta antes**. Tres dudas habituales: que sea
placeholder deliberado, que algo lo use dinámicamente, o que prefieras
mantenerlo.

**¿Hay que actualizar `docs/`?**
Sí, si tocaste la API o el modelo de datos. `docs/api.md` y `docs/database.md`
se desincronizan solos.

**Un análisis previo dice que algo no existe. ¿Le creo?**
No. Este proyecto ya recibió un análisis que afirmó que no había tests, y
había 154. Verifica con `git grep` antes de refactorizar.

---

## Lo que no debes hacer

- No crees `settings.py`, no toques `config/settings/test.py`.
- No añadas linter, formateador ni hooks: el proyecto no los tiene y añadirlos
  reformatea el repo entero.
- No conviertas datos de contacto en literales dentro de templates. Vienen de
  settings por `site_settings`.
- No elimines `agents` de este directorio ni lo muevas a otra carpeta sin
  preguntar: lo dicho aquí es específico de este proyecto.
