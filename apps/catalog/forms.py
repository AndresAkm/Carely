from django import forms

from .models import Category, Product


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


class ProductForm(DashboardFormMixin, forms.ModelForm):
    class Meta:
        model = Product
        fields = ['category', 'name', 'description', 'price', 'image', 'stock', 'is_active', 'featured']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'image': forms.ClearableFileInput(),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'featured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ProductFilterForm(forms.Form):
    q = forms.CharField(label='Buscar', required=False, widget=forms.TextInput(attrs={'placeholder': 'Nombre o descripción...'}))
    category = forms.ModelChoiceField(label='Categoría', queryset=Category.objects.all(), required=False)
    is_active = forms.ChoiceField(label='Estado', choices=[('', 'Todos'), ('True', 'Activo'), ('False', 'Inactivo')], required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')
