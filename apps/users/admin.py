from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CarelyUserAdmin(UserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'role', 'phone', 'is_active', 'is_staff')
    list_filter = ('role', 'is_active', 'is_staff', 'is_superuser')
    search_fields = ('email', 'first_name', 'last_name', 'phone')
    ordering = ('email',)
    fieldsets = UserAdmin.fieldsets + (
        ('Información adicional', {'fields': ('phone', 'role')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Información adicional', {'fields': ('phone', 'role')}),
    )

    def has_delete_permission(self, request, obj=None):
        # User deletion is intentionally centralized in the dashboard force-delete flow.
        return False
