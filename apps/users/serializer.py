import re

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from .models import Address, City, Department, User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'phone', 'role', 'is_active', 'date_joined', 'accepted_terms_at', 'terms_version']
        read_only_fields = ['id', 'username', 'role', 'is_active', 'date_joined', 'is_staff', 'is_superuser']


class RegisterSerializer(serializers.Serializer):
    """Alta de clientes desde la app móvil.

    Replica las validaciones de `RegisterForm` (contraseña y aceptación de
    términos) para que una cuenta creada por la API sea equivalente a una
    creada desde la web.
    """

    first_name = serializers.CharField(max_length=30)
    last_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    phone = serializers.CharField(
        max_length=20, required=False, allow_blank=True, allow_null=True,
    )
    password1 = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True)
    accept_terms = serializers.BooleanField()

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('Este correo electrónico ya está registrado.')
        return value

    def validate_password1(self, value):
        if not re.search(r'[A-Z]', value):
            raise serializers.ValidationError('La contraseña debe contener al menos una mayúscula.')
        if not re.search(r'[a-z]', value):
            raise serializers.ValidationError('La contraseña debe contener al menos una minúscula.')
        if not re.search(r'\d', value):
            raise serializers.ValidationError('La contraseña debe contener al menos un número.')
        return value

    def validate(self, attrs):
        if attrs.get('password1') != attrs.get('password2'):
            raise serializers.ValidationError({'password2': 'Las contraseñas no coinciden.'})
        if not attrs.get('accept_terms'):
            raise serializers.ValidationError({
                'accept_terms': (
                    'Debes leer y aceptar los Términos y Condiciones y la '
                    'Política de Privacidad para crear tu cuenta.'
                ),
            })
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        validated_data.pop('accept_terms')
        password = validated_data.pop('password1')
        user = User(**validated_data)
        user.username = validated_data['email']
        user.set_password(password)
        user.accepted_terms_at = timezone.now()
        user.terms_version = settings.TERMS_VERSION
        user.save()
        return user


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Campos que el cliente puede editar de su propia cuenta."""

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone']

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError('Este correo electrónico ya está registrado.')
        return value

    def update(self, instance, validated_data):
        email = validated_data.get('email')
        if email:
            validated_data['username'] = email
        return super().update(instance, validated_data)


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'api_id', 'name']


class CitySerializer(serializers.ModelSerializer):
    department_id = serializers.IntegerField(source='department.id', read_only=True)

    class Meta:
        model = City
        fields = ['id', 'api_id', 'name', 'department_id']


class AddressSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    city = serializers.PrimaryKeyRelatedField(queryset=City.objects.all())
    department = serializers.PrimaryKeyRelatedField(queryset=Department.objects.all())
    city_name = serializers.CharField(source='city.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model = Address
        fields = [
            'id', 'user', 'recipient_name', 'phone', 'address_line',
            'address_line2', 'city', 'department', 'city_name', 'department_name',
            'postal_code', 'instructions', 'is_default', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

    def validate(self, attrs):
        department = attrs.get('department')
        city = attrs.get('city')
        if department and city and city.department_id != department.pk:
            raise serializers.ValidationError({
                'city': 'El municipio no pertenece al departamento seleccionado.'
            })
        return attrs
