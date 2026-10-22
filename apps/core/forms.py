from django import forms
from django.core.files.uploadedfile import UploadedFile

from apps.catalog.models import Category, Product
from apps.core.models import (
    BENEFIT_POSITIONS,
    MAX_FEATURED_PRODUCTS,
    LandingBenefit,
    SiteCustomization,
    validate_plain_text,
)
from apps.orders.models import Order

MAX_HERO_IMAGE_BYTES = 5 * 1024 * 1024
MAX_LOGO_IMAGE_BYTES = 2 * 1024 * 1024


class ProductChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        estado = '' if obj.is_active else ' (inactivo)'
        return f'{obj.name} · {obj.category.name}{estado}'


class CategoryChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        estado = '' if obj.is_active else ' (inactiva)'
        return f'{obj.name}{estado}'


class SiteCustomizationForm(forms.ModelForm):
    """Portada, productos y categorías destacadas, y pie de página.

    Las selecciones de productos y categorías usan los modelos existentes: el
    campo valida que cada id corresponda a un registro real.
    """

    featured_products = ProductChoiceField(
        label='Productos destacados',
        required=False,
        queryset=Product.objects.select_related('category').order_by('name'),
        widget=forms.CheckboxSelectMultiple,
        help_text=(
            f'Hasta {MAX_FEATURED_PRODUCTS}. Si no eliges ninguno activo, '
            'se muestran los productos marcados como destacados en el catálogo.'
        ),
    )
    featured_categories = CategoryChoiceField(
        label='Categorías destacadas',
        required=False,
        queryset=Category.objects.order_by('order', 'name'),
        widget=forms.CheckboxSelectMultiple,
        help_text='Si no eliges ninguna activa, se muestran todas las categorías activas.',
    )

    class Meta:
        model = SiteCustomization
        fields = [
            'hero_title',
            'hero_subtitle',
            'hero_button_text',
            'hero_image',
            'logo',
            'logo_icon',
            'featured_products',
            'featured_categories',
            'footer_email',
            'footer_phone',
            'footer_address',
            'footer_facebook',
            'footer_instagram',
            'footer_whatsapp',
        ]
        labels = {
            'footer_email': 'Correo de contacto',
            'footer_phone': 'Teléfono',
            'footer_address': 'Dirección',
            'footer_facebook': 'Facebook',
            'footer_instagram': 'Instagram',
            'footer_whatsapp': 'WhatsApp',
        }
        help_texts = {
            'footer_facebook': 'Dejar vacío usa el valor configurado en el servidor.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name not in ('featured_products', 'featured_categories'):
                field.widget.attrs.setdefault('class', 'form-control')

    def _validate_image_size(self, field_name, limit, message):
        image = self.cleaned_data.get(field_name)
        # Solo se mide un archivo recién subido: medir uno ya guardado obligaría
        # a una consulta al almacenamiento en cada guardado.
        if isinstance(image, UploadedFile) and image.size > limit:
            raise forms.ValidationError(message)
        return image

    def clean_hero_image(self):
        return self._validate_image_size(
            'hero_image',
            MAX_HERO_IMAGE_BYTES,
            'La imagen supera 5 MB. Elige una más liviana.',
        )

    def clean_logo(self):
        return self._validate_image_size(
            'logo',
            MAX_LOGO_IMAGE_BYTES,
            'El logo supera 2 MB. Elige una imagen más liviana.',
        )

    def clean_logo_icon(self):
        return self._validate_image_size(
            'logo_icon',
            MAX_LOGO_IMAGE_BYTES,
            'El isotipo supera 2 MB. Elige una imagen más liviana.',
        )

    def clean_featured_products(self):
        products = self.cleaned_data.get('featured_products') or []
        if len(products) > MAX_FEATURED_PRODUCTS:
            raise forms.ValidationError(f'Puedes destacar hasta {MAX_FEATURED_PRODUCTS} productos.')
        return products


class LandingBenefitsForm(forms.Form):
    """Título y descripción de los cuatro bloques de beneficios."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for position in BENEFIT_POSITIONS:
            self.fields[f'title_{position}'] = forms.CharField(
                label=f'Bloque {position}: título',
                max_length=80,
                validators=[validate_plain_text],
                widget=forms.TextInput(attrs={'class': 'form-control'}),
            )
            self.fields[f'description_{position}'] = forms.CharField(
                label=f'Bloque {position}: descripción',
                max_length=200,
                validators=[validate_plain_text],
                widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            )

    def save(self):
        for position in BENEFIT_POSITIONS:
            LandingBenefit.objects.update_or_create(
                position=position,
                defaults={
                    'title': self.cleaned_data[f'title_{position}'],
                    'description': self.cleaned_data[f'description_{position}'],
                },
            )


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


class ContactReplyForm(forms.Form):
    reply = forms.CharField(
        label='Respuesta',
        error_messages={'required': 'Escribe una respuesta antes de enviarla.'},
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 6,
            'placeholder': 'Escribe la respuesta que se enviará por correo…',
        }),
    )

    def clean_reply(self):
        reply = self.cleaned_data['reply'].strip()
        if len(reply) < 5:
            raise forms.ValidationError('Escribe una respuesta antes de enviarla.')
        return reply


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
