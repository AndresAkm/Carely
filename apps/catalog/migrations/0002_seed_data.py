from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0001_initial'),
    ]

    operations = [
        # Esta migración sembraba 6 categorías y 31 productos genéricos.
        # Se dejó como noop a propósito: el catálogo real se carga con el
        # comando `cargar_catalogo`. El archivo se conserva porque otras
        # migraciones (`cart`, `inventory`, `orders`, `catalog`) dependen de él.
        migrations.RunPython(migrations.RunPython.noop, migrations.RunPython.noop),
    ]
