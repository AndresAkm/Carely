from django import forms

from apps.orders.models import Order


class ReportFilterForm(forms.Form):
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
    status = forms.ChoiceField(
        label='Estado',
        required=False,
        choices=[('', 'Todos los estados'), *Order.Status.choices],
        widget=forms.Select(attrs={'class': 'form-control'}),
    )

    def clean(self):
        cleaned_data = super().clean()
        created_from = cleaned_data.get('created_from')
        created_to = cleaned_data.get('created_to')
        if created_from and created_to and created_from > created_to:
            self.add_error('created_to', 'La fecha final debe ser posterior a la fecha inicial.')
        return cleaned_data
