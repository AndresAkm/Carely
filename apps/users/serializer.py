from rest_framework import serializers

from .models import Address, City, Department, User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'phone', 'role', 'is_active', 'date_joined']
        read_only_fields = ['id', 'username', 'role', 'is_active', 'date_joined', 'is_staff', 'is_superuser']


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
