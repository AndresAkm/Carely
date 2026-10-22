from django.contrib import admin

from .models import ContactRequest


@admin.register(ContactRequest)
class ContactRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'email', 'subject', 'status', 'created_at', 'replied_by']
    list_filter = ['status', 'created_at']
    search_fields = ['name', 'email', 'subject', 'message']
    readonly_fields = ['created_at', 'updated_at', 'replied_at', 'replied_by']
    ordering = ['-created_at']
    fieldsets = (
        ('Solicitud', {'fields': ('name', 'email', 'subject', 'message', 'created_at')}),
        ('Respuesta', {'fields': ('status', 'reply', 'replied_at', 'replied_by')}),
        ('Metadatos', {'fields': ('updated_at',)}),
    )
