import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.users.models import City, Department

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


class Command(BaseCommand):
    help = (
        'Carga departamentos y municipios de Colombia desde api-colombia.com '
        'en las tablas Department y City.'
    )

    def handle(self, *args, **options):
        self.stdout.write('Consultando departamentos...')
        departments_raw = _fetch_json(DEPARTMENTS_URL)
        self.stdout.write('Consultando municipios...')
        cities_raw = _fetch_json(CITIES_URL)

        with transaction.atomic():
            departments_by_api_id = {
                item['id']: Department(api_id=item['id'], name=item['name'])
                for item in departments_raw
            }

            if departments_by_api_id:
                Department.objects.bulk_create(
                    departments_by_api_id.values(),
                    update_conflicts=True,
                    update_fields=['name'],
                )

            persisted_departments = {
                dept.api_id: dept
                for dept in Department.objects.filter(
                    api_id__in=departments_by_api_id.keys()
                )
            }

            cities_objects = []
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

            if cities_objects:
                City.objects.bulk_create(
                    cities_objects,
                    update_conflicts=True,
                    update_fields=['name', 'department'],
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'Carga completada: {len(departments_raw)} departamentos, '
                f'{len(cities_objects)} municipios.'
            )
        )
