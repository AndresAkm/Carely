# AGENTS.md

Este repositorio incluye documentación específica para asistentes de IA en
[`Agent/`](Agent/README.md). **Léela antes de modificar nada.**

| Archivo | Contenido |
|---|---|
| [`Agent/ONBOARDING.md`](Agent/ONBOARDING.md) | Orden de lectura para la primera sesión |
| [`Agent/AGENTS.md`](Agent/AGENTS.md) | Reglas obligatorias de trabajo |
| [`Agent/ARCHITECTURE.md`](Agent/ARCHITECTURE.md) | Mapa del proyecto: apps, modelos, rutas, API |
| [`Agent/CONVENTIONS.md`](Agent/CONVENTIONS.md) | Estilo del código, con ejemplos reales |
| [`Agent/RECIPES.md`](Agent/RECIPES.md) | Cómo implementar cada tipo de cambio |
| [`Agent/GOTCHAS.md`](Agent/GOTCHAS.md) | Errores frecuentes y huecos conocidos |

## Lo esencial

```powershell
# Verificar (obligatorio antes de dar por terminado algo)
.\Agent\verify.ps1

# Tests
$env:DJANGO_ENV='test'; .\env\Scripts\python.exe manage.py test
```

- Usa `.\env\Scripts\python.exe`. El Python global no tiene Django.
- `DJANGO_ENV` elige los settings: `development`, `test` o `production`.
- Los tests **solo** funcionan con `DJANGO_ENV=test` (SQLite). Con `development`
  intentan crear la base en MySQL y fallan con `Access denied`.
- Las migraciones se generan con `DJANGO_ENV=development`. En `test` están
  deshabilitadas y `makemigrations` falla.
- Todo el texto visible está en **español**, incluidos `verbose_name` y
  mensajes de error.
- No hay linter ni formateador configurados: revisa tu propio diff.
- No hagas commit ni stagees nada sin que te lo pidan.
