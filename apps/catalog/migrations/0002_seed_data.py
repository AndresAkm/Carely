from django.db import migrations
from django.utils.text import slugify


def seed_data(apps, schema_editor):
    Category = apps.get_model('catalog', 'Category')
    Product = apps.get_model('catalog', 'Product')

    categories_data = [
        {'name': 'Cuidado Facial', 'description': 'Limpieza, hidratación y tratamiento para tu rostro.', 'icon': 'bi-emoji-wink', 'order': 0},
        {'name': 'Cuidado Corporal', 'description': 'Lociones, cremas y aceites para todo tu cuerpo.', 'icon': 'bi-person-arms-up', 'order': 1},
        {'name': 'Cuidado Capilar', 'description': 'Shampoos, acondicionadores y tratamientos para tu cabello.', 'icon': 'bi-scissors', 'order': 2},
        {'name': 'Maquillaje', 'description': 'Bases, labiales y productos de maquillaje profesional.', 'icon': 'bi-palette', 'order': 3},
        {'name': 'Fragancias', 'description': 'Perfumes y colonias para todas las ocasiones.', 'icon': 'bi-flower1', 'order': 4},
        {'name': 'Protección Solar', 'description': 'Protectores solares y cuidados para exponerte al sol.', 'icon': 'bi-sun', 'order': 5},
    ]

    categories = {}
    for cat_data in categories_data:
        cat, _ = Category.objects.get_or_create(
            slug=slugify(cat_data['name']),
            defaults=cat_data,
        )
        categories[cat.name] = cat

    products_data = [
        # Cuidado Facial
        {'name': 'Limpiador Facial Suave', 'description': 'Limpiador facial con ingredientes naturales que remueve impurezas sin resecar la piel.', 'price': 189.00, 'category': categories['Cuidado Facial'], 'stock': 25, 'featured': True},
        {'name': 'Sérum de Ácido Hialurónico', 'description': 'Sérum hidratante con ácido hialurónico para una piel más tersa y luminosa.', 'price': 349.00, 'category': categories['Cuidado Facial'], 'stock': 18, 'featured': True},
        {'name': 'Crema Hidratante No Comedogénica', 'description': 'Crema ligera de absorción rápida ideal para piel mixta y grasa.', 'price': 259.00, 'category': categories['Cuidado Facial'], 'stock': 30},
        {'name': 'Contorno de Ojos con Vitamina C', 'description': 'Tratamiento para el contorno de ojos que reduce ojeras y líneas de expresión.', 'price': 279.00, 'category': categories['Cuidado Facial'], 'stock': 12},
        {'name': 'Mascarilla Facial de Arcilla', 'description': 'Mascarilla purificante con arcilla verde que elimina toxinas y destapa poros.', 'price': 149.00, 'category': categories['Cuidado Facial'], 'stock': 40},
        {'name': 'Tónico Facial con Rosa Mosqueta', 'description': 'Tónico refrescante que equilibra el pH de la piel y aporta luminosidad.', 'price': 179.00, 'category': categories['Cuidado Facial'], 'stock': 22},

        # Cuidado Corporal
        {'name': 'Crema Corporal de Manteca de Karité', 'description': 'Crema nutritiva con manteca de karité para una hidratación profunda y duradera.', 'price': 219.00, 'category': categories['Cuidado Corporal'], 'stock': 20, 'featured': True},
        {'name': 'Aceite Corporal Seco de Almendras', 'description': 'Aceite seco de rápida absorción que nutre y suaviza la piel sin sensación grasosa.', 'price': 239.00, 'category': categories['Cuidado Corporal'], 'stock': 15},
        {'name': 'Exfoliante Corporal de Café', 'description': 'Exfoliante natural con granos de café que renueva la piel y combate la celulitis.', 'price': 199.00, 'category': categories['Cuidado Corporal'], 'stock': 28},
        {'name': 'Loción Reafirmante', 'description': 'Loción con colágeno y elastina que mejora la firmeza y elasticidad de la piel.', 'price': 289.00, 'category': categories['Cuidado Corporal'], 'stock': 10},
        {'name': 'Gel de Baño con Avena y Miel', 'description': 'Gel de baño suave con avena y miel que limpia sin resecar.', 'price': 139.00, 'category': categories['Cuidado Corporal'], 'stock': 35},

        # Cuidado Capilar
        {'name': 'Shampoo Fortalecedor con Biotina', 'description': 'Shampoo enriquecido con biotina que fortalece el cabello desde la raíz.', 'price': 169.00, 'category': categories['Cuidado Capilar'], 'stock': 22, 'featured': True},
        {'name': 'Acondicionador Reparador de Keratina', 'description': 'Acondicionador con keratina que repara el cabello dañado y sella las puntas.', 'price': 179.00, 'category': categories['Cuidado Capilar'], 'stock': 18},
        {'name': 'Mascarilla Capilar de Argán', 'description': 'Mascarilla nutritiva con aceite de argán que devuelve la vida al cabello seco.', 'price': 229.00, 'category': categories['Cuidado Capilar'], 'stock': 14},
        {'name': 'Aceite Capilar de Coco', 'description': 'Aceite multifuncional de coco para hidratar, domar el frizz y dar brillo.', 'price': 129.00, 'category': categories['Cuidado Capilar'], 'stock': 30},
        {'name': 'Spray Protector Térmico', 'description': 'Spray que protege el cabello del calor de secadores y planchas hasta 230°C.', 'price': 159.00, 'category': categories['Cuidado Capilar'], 'stock': 20},

        # Maquillaje
        {'name': 'Base Líquida de Cobertura Natural', 'description': 'Base ligera de acabado natural con protección solar SPF 20.', 'price': 299.00, 'category': categories['Maquillaje'], 'stock': 16, 'featured': True},
        {'name': 'Paleta de Sombras 12 Tonos', 'description': 'Paleta con 12 sombras de alta pigmentación en tonos neutros y vibrantes.', 'price': 429.00, 'category': categories['Maquillaje'], 'stock': 8},
        {'name': 'Labial Mate de Larga Duración', 'description': 'Labial mate de larga duración con fórmula hidratante y colores intensos.', 'price': 159.00, 'category': categories['Maquillaje'], 'stock': 25},
        {'name': 'Máscara de Pestañas Voluminizadora', 'description': 'Máscara que aporta volumen extremo y alarga las pestañas sin grumos.', 'price': 189.00, 'category': categories['Maquillaje'], 'stock': 20},
        {'name': 'Iluminador en Crema', 'description': 'Iluminador cremoso que da un brillo natural y saludable a tu piel.', 'price': 219.00, 'category': categories['Maquillaje'], 'stock': 12},
        {'name': 'Correctivo Líquido Alta Cobertura', 'description': 'Correctivo que cubre ojeras e imperfecciones con acabado natural.', 'price': 169.00, 'category': categories['Maquillaje'], 'stock': 18},

        # Fragancias
        {'name': 'Perfume Floral de Rosas y Jazmín', 'description': 'Fragancia femenina con notas de rosas, jazmín y un toque de vainilla.', 'price': 549.00, 'category': categories['Fragancias'], 'stock': 10, 'featured': True},
        {'name': 'Colonia Cítrica Fresca', 'description': 'Colonia ligera con notas cítricas de naranja, limón y mandarina.', 'price': 329.00, 'category': categories['Fragancias'], 'stock': 15},
        {'name': 'Perfume Amaderado con Sándalo', 'description': 'Fragancia cálida y sofisticada con notas de sándalo, ámbar y lavanda.', 'price': 599.00, 'category': categories['Fragancias'], 'stock': 7},
        {'name': 'Aroma Ambiente de Lavanda', 'description': 'Spray aromatizante con aceites esenciales de lavanda para un ambiente relajante.', 'price': 119.00, 'category': categories['Fragancias'], 'stock': 30},

        # Protección Solar
        {'name': 'Protector Solar Facial SPF 50+', 'description': 'Protector solar de amplio espectro con textura ligera y sin residuo blanco.', 'price': 249.00, 'category': categories['Protección Solar'], 'stock': 20, 'featured': True},
        {'name': 'Bronceador Gradual con SPF 30', 'description': 'Bronceador gradual que protege mientras te da un tono dorado natural.', 'price': 269.00, 'category': categories['Protección Solar'], 'stock': 14},
        {'name': 'After Sun con Aloe Vera', 'description': 'Gel refrescante con aloe vera que calma e hidrata la piel después del sol.', 'price': 159.00, 'category': categories['Protección Solar'], 'stock': 25},
        {'name': 'Protector Solar Corporal Resistente al Agua SPF 50', 'description': 'Protección solar resistente al agua ideal para playa y actividades al aire libre.', 'price': 219.00, 'category': categories['Protección Solar'], 'stock': 18},
        {'name': 'Barra Protectora Labial SPF 30', 'description': 'Protector solar en barra para labios con vitamina E y sabor natural.', 'price': 79.00, 'category': categories['Protección Solar'], 'stock': 40},
    ]

    for prod_data in products_data:
        Product.objects.get_or_create(
            slug=slugify(prod_data['name']),
            defaults=prod_data,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_data),
    ]
