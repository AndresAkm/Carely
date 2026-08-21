from django import forms

from .models import Order


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
