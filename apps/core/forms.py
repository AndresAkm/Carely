from django import forms

from apps.orders.models import Order


class ContactMessageForm(forms.Form):
    name = forms.CharField(
        label='Nombre',
        max_length=120,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '¿Cómo te llamas?',
            'autocomplete': 'name',
        }),
    )
    email = forms.EmailField(
        label='Correo',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'tu@correo.com',
            'autocomplete': 'email',
        }),
    )
    subject = forms.CharField(
        label='Asunto',
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '¿Sobre qué quieres hablar? (opcional)',
        }),
    )
    message = forms.CharField(
        label='Mensaje',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Cuéntanos tu duda con el mayor detalle posible…',
        }),
    )

    def clean_message(self):
        message = self.cleaned_data['message'].strip()
        if len(message) < 10:
            raise forms.ValidationError('Cuéntanos un poco más para poder ayudarte (mínimo 10 caracteres).')
        return message


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
