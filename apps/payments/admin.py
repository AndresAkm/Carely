from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'order',
        'reference',
        'gateway',
        'amount',
        'payment_method',
        'status',
        'transaction_id',
        'processed_at',
    ]
    list_filter = ['gateway', 'payment_method', 'status', 'created_at']
    search_fields = ['reference', 'transaction_id', 'order__user__email']
    autocomplete_fields = ['order']
    readonly_fields = [
        'order',
        'reference',
        'gateway',
        'amount',
        'transaction_id',
        'metadata',
        'processed_at',
        'created_at',
        'updated_at',
    ]
    fieldsets = [
        ('Pago', {'fields': ('order', 'reference', 'gateway', 'amount', 'payment_method')}),
        ('Respuesta de la pasarela', {
            'fields': ('transaction_id', 'status', 'status_message', 'metadata'),
        }),
        ('Fechas', {'fields': ('processed_at', 'created_at', 'updated_at')}),
    ]