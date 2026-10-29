from rest_framework import serializers
from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    """
    Vista de solo lectura del pago.

    `reference`, `metadata` y `status_message` cuentan cosas de la pasarela que
    el cliente no necesita: `metadata` guarda respuestas crudas de Wompi y
    filtrarlo solo en la vista es peor que no exponerlo.
    """

    estado_texto = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id',
            'order',
            'reference',
            'gateway',
            'amount',
            'payment_method',
            'status',
            'estado_texto',
            'created_at',
        ]
        read_only_fields = fields