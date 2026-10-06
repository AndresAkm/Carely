import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import unicodedata

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.users.models import Address, City, Department

DEPARTMENTS_URL = os.environ.get(
    'COLOMBIA_DEPARTMENTS_URL',
    'https://api-colombia.com/api/v1/Department',
)
CITIES_URL = os.environ.get(
    'COLOMBIA_CITIES_URL',
    'https://api-colombia.com/api/v1/City',
)


def _fetch_json(url: str) -> list:
    """Realiza un GET y retorna la respuesta JSON como lista."""
    try:
        with urlopen(url, timeout=60) as response:
            return json.loads(response.read().decode('utf-8'))
    except HTTPError as error:
        raise CommandError(
            f'La API respondió con error HTTP {error.code} al consultar {url}.'
        ) from error
    except URLError as error:
        raise CommandError(
            f'No fue posible contactar la API {url}: {error.reason}'
        ) from error
    except (json.JSONDecodeError, TypeError) as error:
        raise CommandError(
            f'La API devolvió una respuesta JSON inválida desde {url}.'
        ) from error


def _upsert(model, objetos: list, campos_actualizados: list[str]) -> int:
    """
    Inserta lo que no existe y actualiza lo que ya está, usando `api_id` como
    clave.

    No se usa `bulk_create(update_conflicts=True)` a propósito: la sintaxis del
    upsert no es igual en todos los motores. MariaDB no acepta
    `unique_fields` y SQLite sí lo exige, así que el comando funcionaba en
    desarrollo pero reventaba en las pruebas. Separar el alta de la
    actualización usa el mismo SQL en todas partes.
    """
    if not objetos:
        return 0

    existentes = {
        obj.api_id: obj
        for obj in model.objects.filter(api_id__in=[o.api_id for o in objetos])
    }

    nuevos, a_actualizar = [], []
    for objeto in objetos:
        actual = existentes.get(objeto.api_id)
        if actual is None:
            nuevos.append(objeto)
            continue
        if any(getattr(actual, campo) != getattr(objeto, campo) for campo in campos_actualizados):
            for campo in campos_actualizados:
                setattr(actual, campo, getattr(objeto, campo))
            a_actualizar.append(actual)

    if nuevos:
        model.objects.bulk_create(nuevos)
    if a_actualizar:
        model.objects.bulk_update(a_actualizar, campos_actualizados)

    return len(nuevos) + len(a_actualizar)


def _consolida_duplicados() -> int:
    """
    Reapunta los registros que no vienen de la API hacia su equivalente real.

    Antes de esta carga se cargaban a mano un par de lugares con `api_id = -1`.
    La API usa los ids oficiales, así que el nombre quedaba repetido en los
    selectores: dos Antioquia, dos Amagá, y cada usuario con direcciones en la
    fila vieja.

    No se puede borrar la fila vieja porque Address apunta a Department y City
    con PROTECT. Primero se mueven las direcciones al registro de la API y
    recién después se elimina el sobrante.
    """
    unificados = 0

    for local in Department.objects.filter(api_id__lt=0):
        oficial = Department.objects.filter(
            name__iexact=local.name,
        ).exclude(pk=local.pk).exclude(api_id__lt=0).first()

        if oficial is None:
            continue

        Address.objects.filter(department=local).update(department=oficial)
        City.objects.filter(department=local).update(department=oficial)
        # La ciudad repetida se resuelve más abajo, una vez movidas las
        # direcciones que dependían del departamento viejo.
        local.delete()
        unificados += 1

    for local in City.objects.filter(api_id__lt=0):
        oficial = City.objects.filter(
            name__iexact=local.name,
            department__api_id__gte=0,
        ).exclude(pk=local.pk).first()

        if oficial is None:
            continue

        Address.objects.filter(city=local).update(city=oficial)
        local.delete()
        unificados += 1

    return unificados


class Command(BaseCommand):
    help = (
        'Carga departamentos y municipios de Colombia desde api-colombia.com '
        'en las tablas Department y City.'
    )

    def handle(self, *args, **options):
        # `verbosity=0` calla todo lo que el comando reporta. Sin esto, cada
        # prueba que ejercite la carga llena el reporte de la suite con texto
        # que no ayuda a nadie.
        if options['verbosity'] >= 1:
            self.stdout.write('Consultando departamentos...')
        departments_raw = _fetch_json(DEPARTMENTS_URL)
        if options['verbosity'] >= 1:
            self.stdout.write('Consultando municipios...')
        cities_raw = _fetch_json(CITIES_URL)

        with transaction.atomic():
            departments_objects = [
                Department(api_id=item['id'], name=item['name'])
                for item in departments_raw
            ]
            departamentos_guardados = _upsert(
                Department, departments_objects, ['name'],
            )

            persisted_departments = {
                dept.api_id: dept
                for dept in Department.objects.filter(
                    api_id__in=[d.api_id for d in departments_objects]
                )
            }

            cities_objects = []
            # Un municipio sin departamento en la respuesta no se puede
            # guardar: department_id es obligatorio.
            for item in cities_raw:
                department = persisted_departments.get(item.get('departmentId'))
                if department is None:
                    continue
                cities_objects.append(
                    City(
                        api_id=item['id'],
                        name=item['name'],
                        department=department,
                    )
                )

            _upsert(City, cities_objects, ['name', 'department'])

            consolidados = _consolida_duplicados()

        if options['verbosity'] < 1:
            return

        self.stdout.write(
            f'Departamentos: {len(departments_raw)} en la API, '
            f'{departamentos_guardados} escritos.'
        )

        self.stdout.write(
            self.style.SUCCESS(
                f'Carga completada: {Department.objects.count()} departamentos, '
                f'{City.objects.count()} municipios en la base de datos.'
            )
        )
        if consolidados:
            self.stdout.write(
                self.style.WARNING(
                    f'Se unificaron {consolidados} registros duplicados que no '
                    f'venían de la API.'
                )
            )
