from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import SetPasswordForm
import re

User = get_user_model()


class LoginForm(forms.Form):
    email = forms.EmailField(
        label='Correo electrónico',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'tu@correo.com',
            'autocomplete': 'email',
        })
    )
    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '••••••••',
            'autocomplete': 'current-password',
        })
    )

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not email:
            raise ValidationError('El correo electrónico es obligatorio.')
        return email


class RegisterForm(forms.ModelForm):
    first_name = forms.CharField(
        label='Nombre',
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Tu nombre',
        })
    )
    last_name = forms.CharField(
        label='Apellidos',
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Tus apellidos',
        })
    )
    email = forms.EmailField(
        label='Correo electrónico',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'tu@correo.com',
            'autocomplete': 'email',
        })
    )
    password1 = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Mínimo 8 caracteres',
            'autocomplete': 'new-password',
        })
    )
    password2 = forms.CharField(
        label='Confirmar contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Repite tu contraseña',
            'autocomplete': 'new-password',
        })
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError('Este correo electrónico ya está registrado.')
        return email

    def clean_password1(self):
        password = self.cleaned_data.get('password1')
        if len(password) < 8:
            raise ValidationError('La contraseña debe tener al menos 8 caracteres.')
        if not re.search(r'[A-Z]', password):
            raise ValidationError('La contraseña debe contener al menos una mayúscula.')
        if not re.search(r'[a-z]', password):
            raise ValidationError('La contraseña debe contener al menos una minúscula.')
        if not re.search(r'\d', password):
            raise ValidationError('La contraseña debe contener al menos un número.')
        return password

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise ValidationError('Las contraseñas no coinciden.')
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email']
        user.email = self.cleaned_data['email']
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Tu nombre',
                'autocomplete': 'given-name',
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Tus apellidos',
                'autocomplete': 'family-name',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'tu@correo.com',
                'autocomplete': 'email',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Número de teléfono',
                'autocomplete': 'tel',
            }),
        }

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError('Ya existe un usuario con este correo electrónico.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = user.email
        if commit:
            user.save()
        return user


class ForceDeleteUserForm(forms.Form):
    email = forms.EmailField(
        label='Correo del usuario',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'usuario@gmail.com',
            'autocomplete': 'off',
        }),
    )

    def clean_email(self):
        email = self.cleaned_data['email']
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            raise ValidationError('No existe un usuario con ese correo electrónico.')
        self.target_user = user
        return email

    def get_target_user(self):
        return self.target_user


class DashboardUserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'role', 'is_active']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError('Ya existe un usuario con este correo electrónico.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = user.email
        user.is_staff = user.role == User.Role.ADMIN or user.is_superuser
        if commit:
            user.save()
        return user


class DashboardUserCreateForm(DashboardUserForm):
    password1 = forms.CharField(label='Contraseña', widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    password2 = forms.CharField(label='Confirmar contraseña', widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    class Meta(DashboardUserForm.Meta):
        fields = DashboardUserForm.Meta.fields + ['password1', 'password2']

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('password1') != cleaned.get('password2'):
            raise ValidationError('Las contraseñas no coinciden.')
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user
