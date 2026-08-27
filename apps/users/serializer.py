from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'phone', 'role', 'is_active', 'date_joined']
        read_only_fields = ['id', 'username', 'role', 'is_active', 'date_joined', 'is_staff', 'is_superuser']
