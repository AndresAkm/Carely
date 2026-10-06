"""
Limpia los renglones vacíos de las direcciones ya guardadas.

`build_address_snapshot` ahora solo incluye las partes con contenido, pero los
pedidos anteriores quedaron con líneas como `CP:` o `Tel:` sin nada detrás. Se
corregen a mano porque el snapshot es texto plano y no se puede volver a leer de
la dirección: el pedido conserva lo que tenía al crearse.
"""

import re

from django.db import migrations

#: Renglones cuyo prefijo quedó pegado a un salto de línea o al final del texto.
RENGLON_VACIO = re.compile(r'^[ \t]*(CP|Tel|Instrucciones):[ \t]*$', re.MULTILINE)


def limpia_direcciones(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')

    for order in Order.objects.exclude(shipping_address='').iterator():
        limpio = RENGLON_VACIO.sub('', order.shipping_address)
        # Al quitar un renglón queda una línea en blanco que antes no existía.
        limpio = '\n'.join(line.strip() for line in limpio.splitlines() if line.strip())
        if limpio != order.shipping_address:
            order.shipping_address = limpio
            order.save(update_fields=['shipping_address'])


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0008_alter_order_notes'),
    ]

    operations = [
        migrations.RunPython(limpia_direcciones, migrations.RunPython.noop),
    ]