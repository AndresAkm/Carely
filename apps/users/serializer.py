from rest_framework import serializers

from .models import Address, User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'phone', 'role', 'is_active', 'date_joined']
        read_only_fields = ['id', 'username', 'role', 'is_active', 'date_joined', 'is_staff', 'is_superuser']


class AddressSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Address
        fields = [
            'id', 'user', 'recipient_name', 'phone', 'address_line',
            'address_line2', 'city', 'department', 'postal_code',
            'instructions', 'is_default', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']
