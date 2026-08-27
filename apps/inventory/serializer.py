from rest_framework import serializers
from .models import *


class InventoryMovementSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryMovement
        fields = '__all__'
        read_only_fields = ['id', 'product', 'created_by', 'created_at', 'updated_at']
