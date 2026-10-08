from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import ProtectedError
from django.utils.text import slugify

from apps.catalog.models import Category, Product

# Nombres de los productos genéricos que crea la migración 0002_seed_data.
# Se borran para que el catálogo quede conformado solo por los productos
# reales; se listan por nombre y no por categoría porque el sitio de producción
# ya tiene esos 31 registros y ningún otro producto.
GENERIC_NAMES = (
    'Limpiador Facial Suave',
    'Sérum de Ácido Hialurónico',
    'Crema Hidratante No Comedogénica',
    'Contorno de Ojos con Vitamina C',
    'Mascarilla Facial de Arcilla',
    'Tónico Facial con Rosa Mosqueta',
    'Crema Corporal de Manteca de Karité',
    'Aceite Corporal Seco de Almendras',
    'Exfoliante Corporal de Café',
    'Loción Reafirmante',
    'Gel de Baño con Avena y Miel',
    'Shampoo Fortalecedor con Biotina',
    'Acondicionador Reparador de Keratina',
    'Mascarilla Capilar de Argán',
    'Aceite Capilar de Coco',
    'Spray Protector Térmico',
    'Base Líquida de Cobertura Natural',
    'Paleta de Sombras 12 Tonos',
    'Labial Mate de Larga Duración',
    'Máscara de Pestañas Voluminizadora',
    'Iluminador en Crema',
    'Correctivo Líquido Alta Cobertura',
    'Perfume Floral de Rosas y Jazmín',
    'Colonia Cítrica Fresca',
    'Perfume Amaderado con Sándalo',
    'Aroma Ambiente de Lavanda',
    'Protector Solar Facial SPF 50+',
    'Bronceador Gradual con SPF 30',
    'After Sun con Aloe Vera',
    'Protector Solar Corporal Resistente al Agua SPF 50',
    'Barra Protectora Labial SPF 30',
)

# Categorías de la misma semilla que no forman parte del catálogo real: no
# tienen imagen y todos sus productos se borran arriba.
GENERIC_CATEGORY_SLUGS = ('maquillaje', 'fragancias')

# Las imágenes ya viven en el bucket de Supabase `carely-images` (subidas desde
# el panel), así que aquí solo se guarda la ruta: Django la resuelve con
# AWS_S3_CUSTOM_DOMAIN y la muestra en el sitio.
CATEGORIES = (
    {
        'name': 'Cuidado Facial',
        'description': 'Limpieza, hidratación y tratamiento para tu rostro.',
        'icon': 'bi-emoji-wink',
        'order': 0,
        'image': 'categories/category-skin-care.jpg',
    },
    {
        'name': 'Cuidado Corporal',
        'description': 'Jabones, lociones y cremas para todo tu cuerpo.',
        'icon': 'bi-person-arms-up',
        'order': 1,
        'image': 'categories/category-body-care.jpg',
    },
    {
        'name': 'Cuidado Capilar',
        'description': 'Shampoos, acondicionadores y tratamientos para tu cabello.',
        'icon': 'bi-scissors',
        'order': 2,
        'image': 'categories/category-hair-care.jpg',
    },
    {
        'name': 'Protección Solar',
        'description': 'Protectores solares faciales y corporales para exponerte al sol.',
        'icon': 'bi-sun',
        'order': 3,
        'image': 'categories/category-sun-protect.jpg',
    },
    {
        'name': 'Autocuidado',
        'description': 'Higiene y bienestar para tu rutina diaria.',
        'icon': 'bi-heart',
        'order': 4,
        'image': 'categories/category-self-care.jpg',
    },
    {
        'name': 'Accesorios',
        'description': 'Cepillos, diademas y complementos para tu cabello.',
        'icon': 'bi-bag',
        'order': 5,
        'image': 'categories/category-accesories-self-care.jpg',
    },
)

# Precios en pesos colombianos. Los que no tienen fuente directa son
# estimaciones del mercado local y se pueden ajustar desde el admin.
PRODUCTS = (
    {
        'name': 'Anthelios UVMune 400 Anti-Manchas FPS50+ x50 ml',
        'brand': 'La Roche-Posay',
        'category': 'Protección Solar',
        'description': (
            'Protector solar fluido de alta protección con filtros UVMune 400, '
            'antimanchas y resistente al agua.'
        ),
        'price': Decimal('143900.00'),
        'stock': 10,
        'featured': True,
        'image': 'products/sun-protect-anthelios-400-la-roche-posay.jpg',
    },
    {
        'name': 'Fusion Water FPS50+ x50 ml',
        'brand': 'ISDIN',
        'category': 'Protección Solar',
        'description': (
            'Fluido solar ultraligero de rápida absorción, resistente al agua '
            'y apto para pieles mixtas.'
        ),
        'price': Decimal('142100.00'),
        'stock': 10,
        'featured': True,
        'image': 'products/sun-protect-fusion-water-isdin.jpg',
    },
    {
        'name': 'Gel Oil Free FPS50+ x50 ml',
        'brand': 'Heliocare',
        'category': 'Protección Solar',
        'description': (
            'Gel solar sin aceites con acabado mate, pensado para pieles grasas '
            'o con tendencia al acné.'
        ),
        'price': Decimal('129900.00'),
        'stock': 8,
        'featured': False,
        'image': 'products/sun-protect-gel-heliocare.jpg',
    },
    {
        'name': 'Protector Solar Corporal FPS50 x200 ml',
        'brand': 'Nivea Sun',
        'category': 'Protección Solar',
        'description': (
            'Leche solar corporal de rápida absorción, resistente al agua y '
            'apta para todo tipo de piel.'
        ),
        'price': Decimal('59900.00'),
        'stock': 15,
        'featured': False,
        'image': 'products/sun-protect-body-fps50-nivea.jpg',
    },
    {
        'name': 'Protector Solar Niños FPS50 x180 ml',
        'brand': 'Dermaglós',
        'category': 'Protección Solar',
        'description': (
            'Protector solar hipoalergénico para la piel sensible de los niños, '
            'resistente al agua y a la arena.'
        ),
        'price': Decimal('69900.00'),
        'stock': 12,
        'featured': False,
        'image': 'products/sun-protect-kids-fps50-dermaglos.jpg',
    },
    {
        'name': 'Shampoo Hair Food Hidratación x300 ml',
        'brand': 'Garnier',
        'category': 'Cuidado Capilar',
        'description': (
            'Shampoo sin siliconas con ingredientes de origen natural que nutre '
            'el cabello seco desde la raíz.'
        ),
        'price': Decimal('33950.00'),
        'stock': 20,
        'featured': True,
        'image': 'products/hair-hydrating-shampoo.jpg',
    },
    {
        'name': 'Acondicionador Reparador Bond Repair x300 ml',
        'brand': "L'Oréal Elvive",
        'category': 'Cuidado Capilar',
        'description': (
            'Acondicionador que repara los enlaces dañados de la fibra capilar '
            'y desenreda sin apelmazar.'
        ),
        'price': Decimal('32900.00'),
        'stock': 18,
        'featured': False,
        'image': 'products/hair-bond-repair-aconditionador.jpg',
    },
    {
        'name': 'Mascarilla Capilar Hair Food x350 ml',
        'brand': 'Garnier',
        'category': 'Cuidado Capilar',
        'description': (
            'Mascarilla nutritiva 3 en 1: úsala como acondicionador, mascarilla '
            'o crema para peinar.'
        ),
        'price': Decimal('35950.00'),
        'stock': 15,
        'featured': True,
        'image': 'products/hair-mask-garnier.jpg',
    },
    {
        'name': 'Sérum Óleo Extraordinario x100 ml',
        'brand': "L'Oréal Elvive",
        'category': 'Cuidado Capilar',
        'description': (
            'Sérum capilar con 6 óleos que aporta brillo, controla el frizz y '
            'protege del calor hasta 230°C.'
        ),
        'price': Decimal('45950.00'),
        'stock': 14,
        'featured': False,
        'image': 'products/hair-serum-loreal.jpg',
    },
    {
        'name': 'Gel de Baño Suave x295 ml',
        'brand': 'Cetaphil',
        'category': 'Cuidado Corporal',
        'description': (
            'Gel de baño para piel seca y sensible que limpia sin resecar y '
            'refuerza la barrera de la piel.'
        ),
        'price': Decimal('64900.00'),
        'stock': 18,
        'featured': False,
        'image': 'products/body-wash-cetaphil.jpg',
    },
    {
        'name': 'Jabón Líquido Corporal Go Fresh x591 ml',
        'brand': 'Dove',
        'category': 'Cuidado Corporal',
        'description': (
            'Jabón líquido corporal con aloe vera y pepino que limpia dejando '
            'la piel suave y fresca.'
        ),
        'price': Decimal('48550.00'),
        'stock': 20,
        'featured': True,
        'image': 'products/liquid-soap-dove.jpg',
    },
    {
        'name': 'Desodorante Invisible Dry x150 ml',
        'brand': 'Dove',
        'category': 'Cuidado Corporal',
        'description': (
            'Desodorante en aerosol que no deja manchas en la ropa y protege '
            'durante 48 horas.'
        ),
        'price': Decimal('22900.00'),
        'stock': 25,
        'featured': False,
        'image': 'products/deodorant-dove.jpg',
    },
    {
        'name': 'Esponja Facial Konjac',
        'brand': 'Carely',
        'category': 'Cuidado Facial',
        'description': (
            'Esponja vegetal konjac que exfolia suavemente y limpia el rostro '
            'sin irritar la piel.'
        ),
        'price': Decimal('15900.00'),
        'stock': 30,
        'featured': False,
        'image': 'products/facial-sponge-konjac.jpg',
    },
    {
        'name': 'Gel Antibacterial x250 ml',
        'brand': 'Carely',
        'category': 'Autocuidado',
        'description': (
            'Gel desinfectante de manos con aloe vera que limpia y hidrata sin '
            'necesidad de agua.'
        ),
        'price': Decimal('12900.00'),
        'stock': 30,
        'featured': False,
        'image': 'products/sanitizing-gel.jpg',
    },
    {
        'name': 'Kit Self-Care',
        'brand': 'Carely',
        'category': 'Autocuidado',
        'description': (
            'Kit de autocuidado con los esenciales para tu rutina de bienestar, '
            'listo para regalar.'
        ),
        'price': Decimal('39900.00'),
        'stock': 10,
        'featured': False,
        'image': 'products/naceser-self-care.webp',
    },
    {
        'name': 'Diadema para el Cabello',
        'brand': 'Carely',
        'category': 'Accesorios',
        'description': (
            'Diadema suave que mantiene el cabello en su lugar sin marcar ni '
            'apretar.'
        ),
        'price': Decimal('9900.00'),
        'stock': 25,
        'featured': False,
        'image': 'products/hair-band.jpg',
    },
    {
        'name': 'Cepillo para el Cabello',
        'brand': 'Carely',
        'category': 'Accesorios',
        'description': (
            'Cepillo de cerdas suaves que desenreda y distribuye los aceites '
            'naturales del cabello.'
        ),
        'price': Decimal('24900.00'),
        'stock': 20,
        'featured': False,
        'image': 'products/hairbrush.jpg',
    },
)


def _delete_or_deactivate(objeto) -> bool:
    """
    Borra el objeto y devuelve True; si algo de su historia lo impide
    (OrderItem e InventoryMovement protegen al producto con PROTECT), lo
    desactiva para que deje de aparecer en el sitio y devuelve False.
    """
    try:
        objeto.delete()
    except ProtectedError:
        if isinstance(objeto, Product):
            objeto.is_active = False
            objeto.stock = 0
            objeto.save(update_fields=['is_active', 'stock'])
        else:
            objeto.is_active = False
            objeto.save(update_fields=['is_active'])
        return False
    return True


class Command(BaseCommand):
    help = (
        'Reemplaza el catálogo genérico de la migración 0002 por las 6 '
        'categorías y 17 productos reales de Carely, con imagen y precio en COP.'
    )

    def handle(self, *args, **options):
        verbosity = options['verbosity']
        genericos = Product.objects.filter(
            slug__in=[slugify(nombre) for nombre in GENERIC_NAMES],
        )

        with transaction.atomic():
            borrados, conservados = 0, 0
            for producto in genericos:
                if _delete_or_deactivate(producto):
                    borrados += 1
                else:
                    conservados += 1

            categorias_borradas, categorias_desactivadas = 0, 0
            for slug in GENERIC_CATEGORY_SLUGS:
                categoria = Category.objects.filter(slug=slug).first()
                if categoria is None:
                    continue
                if _delete_or_deactivate(categoria):
                    categorias_borradas += 1
                else:
                    categorias_desactivadas += 1

            categorias = {}
            for item in CATEGORIES:
                categoria, _ = Category.objects.update_or_create(
                    slug=slugify(item['name']),
                    defaults={**item, 'is_active': True},
                )
                categorias[categoria.name] = categoria

            for item in PRODUCTS:
                # `dict(item, ...)` copia: `item` es una constante de módulo y
                # no se puede ir mutando cada vez que se corre el comando.
                Product.objects.update_or_create(
                    slug=slugify(item['name']),
                    defaults=dict(
                        item,
                        category=categorias[item['category']],
                        is_active=True,
                    ),
                )

        if verbosity < 1:
            return

        self.stdout.write(
            f'Productos genéricos: {borrados} borrados'
            + (f', {conservados} desactivados por tener historial.' if conservados else '.')
        )
        self.stdout.write(
            f'Categorías de la semilla: {categorias_borradas} borradas'
            + (
                f', {categorias_desactivadas} desactivadas por tener productos.'
                if categorias_desactivadas
                else '.'
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'Catálogo listo: {Category.objects.count()} categorías y '
                f'{Product.objects.count()} productos.'
            )
        )
