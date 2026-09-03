from django.db import transaction
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from rest_framework_simplejwt.views import TokenObtainPairView

from ..models import Address, City, Department, User
from ..serializer import AddressSerializer, CitySerializer, DepartmentSerializer, UserSerializer
from apps.core.permissions import IsAdmin, IsAuthenticatedOwnedOrAdmin, is_admin


# Vistas para las APIs
class UserViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdmin]
    queryset = User.objects.all()
    serializer_class = UserSerializer
    http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']

    def get_queryset(self):
        if self.request.user.is_superuser or self.request.user.is_staff or getattr(self.request.user, 'role', None) == User.Role.ADMIN:
            return super().get_queryset()
        return User.objects.filter(pk=self.request.user.pk)


class AddressViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOwnedOrAdmin]
    queryset = Address.objects.all()
    serializer_class = AddressSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if is_admin(self.request.user):
            return queryset
        return queryset.filter(user=self.request.user, is_active=True)

    def perform_create(self, serializer):
        address = serializer.save(user=self.request.user)
        if not Address.objects.filter(user=self.request.user, is_active=True).exclude(pk=address.pk).filter(is_default=True).exists():
            address.is_default = True
            address.save(update_fields=['is_default'])

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.is_default = False
        instance.save(update_fields=['is_active', 'is_default'])

    @action(detail=True, methods=['patch'], url_path='establecer-predeterminada')
    def set_default(self, request, pk=None):
        address = self.get_object()
        if not address.is_active:
            return Response({'detail': 'No se puede establecer como predeterminada una dirección inactiva.'}, status=400)
        with transaction.atomic():
            Address.objects.select_for_update().filter(
                user=request.user,
                is_default=True,
            ).update(is_default=False)
            address.is_default = True
            address.save(update_fields=['is_default'])
        address.refresh_from_db()
        return Response(self.get_serializer(address).data)


class DepartmentViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly]
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer


class CityViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly]
    queryset = City.objects.all()
    serializer_class = CitySerializer
    http_method_names = ['get', 'head', 'options']

    def get_queryset(self):
        queryset = self.queryset
        department = self.request.query_params.get('department')
        if department:
            queryset = queryset.filter(department_id=department)
        return queryset
