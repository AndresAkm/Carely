from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Address, City, Department, TwoFactorCode, User


@admin.register(User)
class CarelyUserAdmin(UserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'role', 'phone', 'is_active', 'is_staff')
    list_filter = ('role', 'is_active', 'is_staff', 'is_superuser', 'two_factor_enabled')
    search_fields = ('email', 'first_name', 'last_name', 'phone')
    ordering = ('email',)
    fieldsets = UserAdmin.fieldsets + (
        ('Información adicional', {'fields': ('phone', 'role')}),
        ('Términos y condiciones', {'fields': ('accepted_terms_at', 'terms_version')}),
        ('Deshabilitación', {'fields': (('deactivated_at', 'deactivated_by'),)}),
        ('Verificación en dos pasos', {'fields': ('two_factor_enabled', 'two_factor_enabled_at')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Información adicional', {'fields': ('phone', 'role')}),
    )

    def has_delete_permission(self, request, obj=None):
        # User deletion is intentionally centralized in the dashboard force-delete flow.
        return False


@admin.register(TwoFactorCode)
class TwoFactorCodeAdmin(admin.ModelAdmin):
    list_display = ['user', 'purpose', 'expires_at', 'used_at', 'failed_attempts', 'created_at']
    list_filter = ['purpose', 'used_at']
    search_fields = ['user__email']
    ordering = ['-created_at']

    def has_add_permission(self, request):
        # Los códigos los genera services.send_two_factor_code, nunca a mano.
        return False

    def has_change_permission(self, request, obj=None):
        # Solo se consulta: editar el hash anularía la verificación del código.
        return False


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ['recipient_name', 'user', 'city', 'department', 'is_active', 'is_default', 'created_at']
    list_filter = ['is_active', 'is_default', 'department']
    search_fields = ['recipient_name', 'user__email', 'city__name', 'address_line']
    autocomplete_fields = ['user', 'city', 'department']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'api_id']
    search_fields = ['name']
    ordering = ['name']


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ['name', 'department', 'api_id']
    list_filter = ['department']
    search_fields = ['name', 'department__name']
    autocomplete_fields = ['department']
    ordering = ['department', 'name']
