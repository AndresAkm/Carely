# Agent — kit de trabajo para asistentes de IA

Esta carpeta es el punto de entrada para cualquier agente que vaya a tocar el
proyecto Carely. Está escrita para que puedas arrancar sin leer todo el código.

## Empieza aquí

Si eres un asistente de IA y no conoces el proyecto, sigue
[`ONBOARDING.md`](ONBOARDING.md) en orden. Resumen de los archivos:

| Si quieres… | Lee |
|---|---|
| Tu primer día aquí | [`ONBOARDING.md`](ONBOARDING.md) |
| Reglas que no debes romper | [`AGENTS.md`](AGENTS.md) |
| Entender cómo está armado el proyecto | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| Saber cómo se ve el código aquí | [`CONVENTIONS.md`](CONVENTIONS.md) |
| Implementar algo concreto paso a paso | [`RECIPES.md`](RECIPES.md) |
| Evitar errores que ya se han pagado | [`GOTCHAS.md`](GOTCHAS.md) |

## Verificación rápida

Desde la raíz del repo:

```powershell
.\Agent\verify.ps1
```

Ejecuta `manage.py check` y la suite completa de tests. **Toda tarea debe
terminar con esto en verde.**

## Contexto mínimo imprescindible

Si solo lees una cosa, lee esto. El resto está en los archivos anteriores.

- **Venv**: siempre `.\env\Scripts\python.exe`. El Python global no tiene Django.
- **Settings**: se elige con `DJANGO_ENV` (`development` | `test` | `production`),
  no con `DJANGO_SETTINGS_MODULE`. Default: `development`.
- **Tests**: `$env:DJANGO_ENV='test'; .\env\Scripts\python.exe manage.py test`
- **Base de datos**: MySQL en todos los entornos salvo `test`, que usa SQLite.
- **Idioma**: toda la interfaz, comments de campo (`verbose_name`) y mensajes de
  error están en **español**. No introduzcas texto en inglés en la UI.
- **Sin linter**: no hay ruff/flake8/black ni hooks pre-commit configurados. Tu
  revisión del diff es la única red. Revísalo.
- **205 tests en verde** antes de tocar nada, para saber que partías de una base sana.

## Reglas de oro

1. No subas nada a Git sin que te lo pidan explícitamente. Ni stagees ni commitees.
2. Corre los tests antes y después de cada cambio.
3. Si añades un modelo, genera la migración — pero con `DJANGO_ENV=development`,
   nunca con `test` (las migraciones están deshabilitadas ahí y falla).
4. Si añades un campo o endpoint, actualiza `docs/` en el mismo commit lógico.
5. Ante la duda entre dos enfoques, elige el que siga una convención que ya
   exista en el código. No introduzcas un patrón nuevo sin motivo.
6. No borres archivos ni hagas refactors grandes si la tarea es acotada. Dímelo
   primero y pregunta.

## Mapa rápido

```
config/      settings por entorno, urls raíz, router de la API
apps/        7 apps Django (core, users, catalog, cart, orders, inventory, payments)
templates/   base.html, navbar, footer, components/  (compartidos)
static/      css y js globales
docs/        api.md, database.md, deployment.md
requirements/ base.txt, development.txt, production.txt
```

Detalles de cada app en [`ARCHITECTURE.md`](ARCHITECTURE.md).
