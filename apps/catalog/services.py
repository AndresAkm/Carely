import logging
from collections import Counter
from io import BytesIO
from pathlib import PurePosixPath
from statistics import median

from django.core.files.base import ContentFile
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

logger = logging.getLogger(__name__)

EXTENSIONES_IMAGEN = frozenset({'.jpg', '.jpeg', '.png', '.webp'})


def nombre_sin_fondo(nombre):
    ruta = PurePosixPath(nombre)
    base = ruta.stem.removesuffix('-sin-fondo')
    return str(ruta.with_name(f'{base}-sin-fondo.webp'))


def _color_de_fondo(imagen):
    ancho, alto = imagen.size
    pixeles = imagen.load()
    paso_x = max(1, ancho // 100)
    paso_y = max(1, alto // 100)

    borde = []
    for x in range(0, ancho, paso_x):
        borde.append(pixeles[x, 0])
        borde.append(pixeles[x, alto - 1])
    for y in range(0, alto, paso_y):
        borde.append(pixeles[0, y])
        borde.append(pixeles[ancho - 1, y])

    cuantizados = Counter((r // 8 * 8, g // 8 * 8, b // 8 * 8) for r, g, b in borde)
    if not cuantizados:
        return None

    base, _ = cuantizados.most_common(1)[0]
    cercanos = [
        color for color in borde
        if max(abs(color[i] - base[i]) for i in range(3)) <= 12
    ]
    if not cercanos:
        return None

    return tuple(int(median(color[i] for color in cercanos)) for i in range(3))


def _es_fondo_claro(color):
    return min(color) >= 200 and max(color) - min(color) <= 24


def _mascara_de_fondo(imagen, color_fondo, umbral):
    diferencia = ImageChops.difference(
        imagen,
        Image.new('RGB', imagen.size, color_fondo),
    )
    rojo, verde, azul = diferencia.split()
    maxima = ImageChops.lighter(ImageChops.lighter(rojo, verde), azul)
    elegible = maxima.point(lambda valor: 255 if valor <= umbral else 0)

    ancho, alto = imagen.size
    pixeles = elegible.load()
    semillas = set()
    for x in range(ancho):
        for y in (0, alto - 1):
            if pixeles[x, y] == 255:
                semillas.add((x, y))
    for y in range(alto):
        for x in (0, ancho - 1):
            if pixeles[x, y] == 255:
                semillas.add((x, y))

    for semilla in semillas:
        if elegible.getpixel(semilla) == 255:
            ImageDraw.floodfill(elegible, semilla, 128)

    return elegible.point(lambda valor: 255 if valor == 128 else 0)


def quitar_fondo_blanco(contenido, umbral=10):
    try:
        original = Image.open(BytesIO(contenido))
        original.load()
    except (OSError, ValueError):
        return None

    if 'A' in original.getbands():
        alfa = original.convert('RGBA').getchannel('A')
        if alfa.getextrema()[0] < 255:
            return None

    imagen = ImageOps.exif_transpose(original).convert('RGB')
    if min(imagen.size) < 16:
        return None

    color_fondo = _color_de_fondo(imagen)
    if color_fondo is None or not _es_fondo_claro(color_fondo):
        return None

    mascara = _mascara_de_fondo(imagen, color_fondo, umbral)
    if mascara.getbbox() is None:
        return None

    alfa = Image.composite(
        Image.new('L', imagen.size, 0),
        Image.new('L', imagen.size, 255),
        mascara,
    )
    alfa = alfa.filter(ImageFilter.GaussianBlur(0.8))

    resultado = imagen.convert('RGBA')
    resultado.putalpha(alfa)

    salida = BytesIO()
    resultado.save(salida, format='WEBP', quality=92, method=6)
    return salida.getvalue(), 'WEBP'


def procesar_imagen_de_producto(imagen):
    if not imagen or getattr(imagen, '_committed', True):
        return None

    try:
        imagen.seek(0)
        contenido = imagen.read()
        resultado = quitar_fondo_blanco(contenido)
    except Exception:
        logger.exception(
            'No se pudo quitar el fondo a la imagen %s',
            getattr(imagen, 'name', ''),
        )
        return None

    if resultado is None:
        return None

    salida, _ = resultado
    return ContentFile(salida, name=nombre_sin_fondo(imagen.name))
