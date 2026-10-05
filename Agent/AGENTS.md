# AGENTS.md — reglas de trabajo

Instrucciones operativas para agentes que modifican este repositorio. Son
normativas: si algo aquí contradice tu impulso por escribir rápido, gana esto.

## 1. Antes de tocar nada

```powershell
$env:DJANGO_ENV='test'; .\env\Scripts\python.exe manage.py test
```

Si la suite **no** pasa en verde antes de tu cambio, no es culpa tuya pero
tampoco puedes atribuírselo a tu cambio. Anótalo y sigue.

Nunca uses el Python del sistema: no tiene Django instalado. El intérprete del
proyecto es `.\env\Scripts\python.exe`.

## 2. Nunca hagas esto

| Prohibido | Por qué |
|---|---|
| `git commit`, `git add`, `git push` sin pedirlo | El control del historial es del usuario. |
| `git checkout -- .`, `git reset --hard`, borrar archivos sin confirmar | Trabajo no solicitada y potencialmente destructiva. |
| Editar `config/settings/test.py` para hacer pasar un test | Es el entorno de pruebas, no un atajo. |
| Desactivar un test o marcarlo `skip` para que la suite pase | Un test que falla es información, no un obstáculo. |
| Poner el password de un campo en claro, o secretos en el código | `.env` está ignorado por Git; ahí van los secretos. |
| Introducir cadenas visibles para el usuario en inglés | La interfaz es enteramente en español. |
| Crear un `settings.py` propio o un `.env` en Git | Rompe el esquema por entorno. |
| Añadir dependencias sin pasar por `requirements/` | Ver §6. |

## 3. Cómo se ejecuta cada cosa

```powershell
# Verificación (obligatoria al terminar)
$env:DJANGO_ENV='test'; .\env\Scripts\python.exe manage.py check
$env:DJANGO_ENV='test'; .\env\Scripts\python.exe manage.py test
.\Agent\verify.ps1

# Migraciones — OJO: nunca con DJANGO_ENV=test, están deshabilitadas
$env:DJANGO_ENV='development'; .\env\Scripts\python.exe manage.py makemigrations
$env:DJANGO_ENV='development'; .\env\Scripts\python.exe manage.py migrate

# Servidor de desarrollo (MySQL, necesita .env con credenciales)
$env:DJANGO_ENV='development'; .\env\Scripts\python.exe manage.py runserver

# Datos de geography
.\env\Scripts\python.exe manage.py cargar_colombia
```

## 4. Flujo de trabajo de un cambio

1. **Lee** el archivo completo y sus vecinos antes de editar. Contexto primero.
2. **Localiza** la convención existente más parecida a lo que vas a escribir y
   cópiala. Este proyecto es consistente; lo nuevo debe serlo también.
3. **Edita** lo mínimo. Nada de reformatear código ajeno mientras editas otra cosa.
4. **Migra** si tocaste modelos, con `DJANGO_ENV=development`.
5. **Testea**, incluido el caso de uso nuevo. Un cambio sin test es medio cambio.
6. **Verifica**: `check` + suite completa.
7. **Revisa tu diff**: `git diff`. Léelo de verdad. Busca restos de acuerdo con
   tu editor, comillas desbalanceadas, acentos corruptos.
8. **Documenta** si el cambio afecta a la API o al esquema de datos.

## 5. Cambios que exigen más cuidado

- **Modelos**: una migración mal pensada no se revierte sola. Di con
  `makemigrations` y revisa el archivo generado antes de aplicarlo.
- **Permisos**: tocar `apps/core/permissions.py` afecta a toda la API. Si
  relajas un permiso, añade un test que demuestre que el caso protegido falla.
- **Señales**: `apps/orders/signals.py` recalcula totales de pedido en
  `post_save`/`post_delete` de `OrderItem`. Si añades otro que toque totales,
  revisas recursión.
- **Context processors**: corren en **todas** las páginas. Un `queryset` sin
  filtro `[:N]` o sin `try/except` degrada el sitio entero y rompe páginas
  anónimas si consulta la BD.
- **Deshabilitación de cuenta**: usa `User.is_active`. No añadas otro mecanismo.

## 6. Dependencias

`requirements/base.txt` es la lista real. Si añades un paquete, va ahí (o en
`production.txt` si solo es de despliegue). `development.txt` no contiene
herramientas de calidad: **no hay linter, ni formateador, ni pre-commit en este
repositorio**. No asumas que un comando de ruff o black va a existir.

Si añades una dependencia que ya está en `base.txt` pero falta en
`production.txt` (`psycopg` es el caso actual), menciónalo en vez de
"arreglarlo" de paso.

## 7. Antes de decir "hecho"

- [ ] `manage.py check` sin issues
- [ ] Suite completa en verde
- [ ] `git diff` leído, sin basura
- [ ] Sin comentarios explicativos del tipo "esto es un parche" o "FIXME"
- [ ] Sin `print()` de depuración
- [ ] Sin archivos `.pyc`, `.log`, ni SQLite de prueba añadidos
- [ ] `docs/` actualizado si tocaste API o datos
- [ ] Sin commit, salvo que te lo pidan

## 8. Estilo de las respuestas

- Español, como el código.
- Sé conciso. Sin preámbulos ni resúmenes de lo obvio.
- Cuando reportes un cambio, di **qué** y **por qué**, y el resultado del
  comando de verificación. No adivines: si no lo ejecutaste, no lo digas.
- Si una tarea quedó a medias, dilo claramente y explica qué falta y por qué.
