from django.contrib import admin, messages

from apps.inventory.admin import InventoryInline

from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'order', 'is_active', 'created_at']
    list_editable = ['order', 'is_active']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']
    list_filter = ['is_active']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price', 'stock', 'featured', 'is_active', 'created_at']
    # stock se elimina de list_editable: su modificación debe ir por InventoryService
    list_editable = ['price', 'featured', 'is_active']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name', 'description']
    list_filter = ['category', 'is_active', 'featured']
    autocomplete_fields = ['category']
    # stock es read-only en el formulario del admin — se modifica vía la API de inventario
    readonly_fields = ['stock', 'created_at', 'updated_at']
    inlines = [InventoryInline]

    fieldsets = [
        (None, {
            'fields': ['name', 'slug', 'category', 'description', 'image'],
        }),
        ('Precio y estado', {
            'fields': ['price', 'featured', 'is_active'],
        }),
        ('Stock (solo lectura — pasa por API /api/v1/inventario/movimientos/)', {
            'fields': ['stock'],
            'classes': ['collapse'],
        }),
        ('Fechas', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse'],
        }),
    ]
