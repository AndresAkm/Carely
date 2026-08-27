from django import forms

from .models import Category, Product
from django.utils.text import slugify


class DashboardFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')


class CategoryForm(DashboardFormMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description', 'icon', 'image', 'order', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'image': forms.ClearableFileInput(),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_name(self):
        name = self.cleaned_data['name']
        existing = Category.objects.filter(slug=slugify(name))
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError('Ya existe una categoría con ese nombre.')
        return name


class ProductForm(DashboardFormMixin, forms.ModelForm):
    category = forms.ModelChoiceField(
        label='Categoría',
        queryset=Category.objects.all(),
        required=False,
        empty_label='Selecciona una categoría',
    )

    class Meta:
        model = Product
        fields = ['category', 'name', 'description', 'price', 'image', 'stock', 'is_active', 'featured']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'image': forms.ClearableFileInput(),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'featured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_name(self):
        name = self.cleaned_data['name']
        existing = Product.objects.filter(slug=slugify(name))
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError('Ya existe un producto con ese nombre.')
        return name


class ProductFilterForm(forms.Form):
    q = forms.CharField(label='Buscar', required=False, widget=forms.TextInput(attrs={'placeholder': 'Nombre o descripción...'}))
    category = forms.ModelChoiceField(label='Categoría', queryset=Category.objects.all(), required=False)
    is_active = forms.ChoiceField(label='Estado', choices=[('', 'Todos'), ('True', 'Activo'), ('False', 'Inactivo')], required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')
