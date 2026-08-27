from django import forms

from .models import Coupon, Order


class OrderFilterForm(forms.Form):
    q = forms.CharField(
        label='Buscar',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Número, cliente o correo',
        }),
    )
    status = forms.ChoiceField(
        label='Estado',
        required=False,
        choices=[('', 'Todos los estados'), *Order.Status.choices],
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    created_from = forms.DateField(
        label='Desde',
        required=False,
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
    )
    created_to = forms.DateField(
        label='Hasta',
        required=False,
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
    )

    def clean(self):
        cleaned_data = super().clean()
        created_from = cleaned_data.get('created_from')
        created_to = cleaned_data.get('created_to')
        if created_from and created_to and created_from > created_to:
            self.add_error('created_to', 'La fecha final debe ser posterior a la fecha inicial.')
        return cleaned_data


class OrderStatusForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['status', 'notes']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Notas internas sobre este pedido',
            }),
        }


class CouponForm(forms.ModelForm):
    """
    Formulario para crear y editar cupones en el dashboard administrativo.
    No duplica reglas de negocio del modelo ni del servicio validate_coupon.
    """

    class Meta:
        model = Coupon
        fields = [
            'code',
            'discount_type',
            'discount_value',
            'minimum_purchase',
            'is_active',
            'usage_limit',
            'valid_from',
            'valid_until',
        ]
        widgets = {
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: CARELY10',
                'style': 'text-transform:uppercase;font-family:monospace;letter-spacing:0.05em;',
            }),
            'discount_type': forms.Select(attrs={'class': 'form-control'}),
            'discount_value': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01',
                'placeholder': 'Ej: 10 (%) o 5000 (fijo)',
            }),
            'minimum_purchase': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0 = sin mínimo',
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'usage_limit': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'placeholder': 'Vacío = ilimitado',
            }),
            'valid_from': forms.DateTimeInput(
                attrs={'class': 'form-control', 'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M',
            ),
            'valid_until': forms.DateTimeInput(
                attrs={'class': 'form-control', 'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M',
            ),
        }
        help_texts = {
            'code': 'Se normalizará automáticamente a mayúsculas.',
            'discount_value': 'Porcentaje (ej: 10 = 10 %) o valor fijo en COP (ej: 5000).',
            'minimum_purchase': 'Subtotal mínimo del carrito para que el cupón aplique.',
            'usage_limit': 'Dejar en blanco para usos ilimitados.',
            'valid_from': 'Dejar vacío para vigencia inmediata.',
            'valid_until': 'Dejar vacío para sin fecha de expiración.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pre-formatear fechas para el input datetime-local
        for field_name in ('valid_from', 'valid_until'):
            if self.instance and self.instance.pk:
                value = getattr(self.instance, field_name)
                if value:
                    self.initial[field_name] = value.strftime('%Y-%m-%dT%H:%M')

    def clean_code(self):
        return self.cleaned_data['code'].strip().upper()

    def clean(self):
        cleaned_data = super().clean()
        valid_from = cleaned_data.get('valid_from')
        valid_until = cleaned_data.get('valid_until')
        if valid_from and valid_until and valid_from >= valid_until:
            self.add_error('valid_until', 'La fecha de expiración debe ser posterior a la fecha de inicio.')

        discount_type = cleaned_data.get('discount_type')
        discount_value = cleaned_data.get('discount_value')
        if discount_type == Coupon.DiscountType.PERCENTAGE and discount_value:
            if discount_value <= 0 or discount_value > 100:
                self.add_error('discount_value', 'El porcentaje debe estar entre 0.01 y 100.')
        return cleaned_data
