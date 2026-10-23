import re
from pathlib import PurePosixPath

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError

from apps.catalog.models import Product
from apps.catalog.services import (
    EXTENSIONES_IMAGEN,
    nombre_sin_fondo,
    quitar_fondo_blanco,
)

SUFIJO_ALEATORIO = re.compile(r'_[A-Za-z0-9]{5,}$')


class Command(BaseCommand):
    help = (
        'Quita el fondo claro de las imágenes de producto, guarda una copia del '
        'original y actualiza la referencia del producto al nuevo archivo.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Informa los cambios sin escribir en el almacenamiento ni en la base de datos.',
        )
        parser.add_argument(
            '--umbral',
            type=int,
            default=10,
            help='Diferencia máxima por canal para considerar un píxel parte del fondo (0-255).',
        )
        parser.add_argument(
            '--limite',
            type=int,
            default=0,
            help='Procesa como máximo esta cantidad de imágenes. 0 significa todas.',
        )
        parser.add_argument(
            '--producto',
            type=int,
            default=None,
            help='Procesa únicamente el producto con este ID.',
        )
        parser.add_argument(
            '--sin-respaldo',
            action='store_true',
            help='No guarda una copia del original en _originales/.',
        )
        parser.add_argument(
            '--no-reparar-referencias',
            action='store_true',
            help='No intenta resolver rutas que no existen en el almacenamiento.',
        )

    def handle(self, *args, **options):
        if not 0 <= options['umbral'] <= 255:
            raise CommandError('El umbral debe estar entre 0 y 255.')

        storage = default_storage
        productos = Product.objects.exclude(image='').exclude(image__isnull=True).order_by('pk')
        if options['producto'] is not None:
            productos = productos.filter(pk=options['producto'])
            if not productos.exists():
                raise CommandError(
                    f'No existe un producto con imagen e ID {options["producto"]}.'
                )

        limite = options['limite'] or None
        reparar = not options['no_reparar_referencias']
        dry_run = options['dry_run']
        verbosity = options['verbosity']

        procesadas = 0
        omitidas = 0
        reparadas = 0
        errores = []
        mapeo = {}

        for producto in productos:
            if limite is not None and procesadas >= limite:
                break

            nombre_original = producto.image.name
            if nombre_original in mapeo:
                nuevo = mapeo[nombre_original]
                if not dry_run:
                    Product.objects.filter(pk=producto.pk).update(image=nuevo)
                self._log(verbosity, f'{nombre_original} -> {nuevo} (ya procesada)')
                continue

            nombre = nombre_original
            if not storage.exists(nombre):
                if not reparar:
                    errores.append(f'{nombre_original}: no existe en el almacenamiento')
                    continue
                reparado = self._resolver_faltante(storage, nombre)
                if reparado is None:
                    errores.append(
                        f'{nombre_original}: no existe y no se encontró un reemplazo inequívoco'
                    )
                    continue
                if verbosity >= 1:
                    self.stdout.write(
                        self.style.WARNING(f'Referencia reparada: {nombre_original} -> {reparado}')
                    )
                if not dry_run:
                    Product.objects.filter(pk=producto.pk).update(image=reparado)
                nombre = reparado
                reparadas += 1

            ruta = PurePosixPath(nombre)
            if ruta.suffix.lower() not in EXTENSIONES_IMAGEN:
                omitidas += 1
                self._log(verbosity, f'{nombre}: formato no soportado, se omite')
                continue

            try:
                with storage.open(nombre, 'rb') as archivo:
                    contenido = archivo.read()
                resultado = quitar_fondo_blanco(contenido, options['umbral'])
            except Exception as exc:
                errores.append(f'{nombre}: {exc}')
                continue

            if resultado is None:
                omitidas += 1
                self._log(
                    verbosity,
                    f'{nombre}: sin cambios (ya es transparente o el fondo no es claro)',
                )
                continue

            salida, formato = resultado
            nuevo = nombre_sin_fondo(nombre)

            if dry_run:
                self._log(
                    verbosity,
                    f'[dry-run] {nombre} -> {nuevo} ({formato}, '
                    f'{len(contenido)} -> {len(salida)} bytes)',
                )
                mapeo[nombre_original] = nuevo
                mapeo[nombre] = nuevo
                procesadas += 1
                continue

            try:
                if not options['sin_respaldo']:
                    respaldo = f'_originales/{nombre}'
                    if not storage.exists(respaldo):
                        storage.save(respaldo, ContentFile(contenido))
                guardado = storage.save(nuevo, ContentFile(salida))
                Product.objects.filter(pk=producto.pk).update(image=guardado)
            except Exception as exc:
                errores.append(f'{nombre}: {exc}')
                continue

            mapeo[nombre_original] = guardado
            mapeo[nombre] = guardado
            procesadas += 1
            self._log(
                verbosity,
                f'{nombre} -> {guardado} ({formato}, {len(contenido)} -> {len(salida)} bytes)',
            )

        if verbosity >= 1:
            self.stdout.write('')
            self.stdout.write(
                f'Imágenes procesadas: {procesadas}. '
                f'Omitidas: {omitidas}. Referencias reparadas: {reparadas}. '
                f'Errores: {len(errores)}.'
            )
            if dry_run:
                self.stdout.write(self.style.WARNING('Modo dry-run: no se escribió nada.'))
            for error in errores:
                self.stderr.write(self.style.ERROR(error))

    def _log(self, verbosity, mensaje):
        if verbosity >= 1:
            self.stdout.write(mensaje)

    def _resolver_faltante(self, storage, nombre):
        ruta = PurePosixPath(nombre)
        base = SUFIJO_ALEATORIO.sub('', ruta.stem)
        candidatos = []
        for extension in (ruta.suffix.lower(), '.jpg', '.jpeg', '.png', '.webp'):
            candidato = str(ruta.with_name(f'{base}{extension}'))
            if candidato != nombre and storage.exists(candidato):
                candidatos.append(candidato)

        unicos = list(dict.fromkeys(candidatos))
        if len(unicos) == 1:
            return unicos[0]
        return None
