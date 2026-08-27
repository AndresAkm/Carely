from django.contrib import admin
from .models import Coupon, Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    autocomplete_fields = ['product']
    readonly_fields = ['product_name', 'unit_price', 'subtotal']

    def subtotal(self, obj):
        return f'COP {obj.subtotal:,.2f}'
    subtotal.short_description = 'Subtotal'


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'status', 'coupon_code', 'discount_amount', 'total', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['user__email', 'shipping_address', 'coupon_code']
    autocomplete_fields = ['user']
    readonly_fields = ['created_at', 'updated_at', 'coupon_code', 'discount_amount', 'coupon']
    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['order', 'product', 'product_name', 'quantity', 'unit_price']
    search_fields = ['order__user__email', 'product__name']
    autocomplete_fields = ['order', 'product']


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = [
        'code', 'discount_type', 'discount_value', 'is_active',
        'usage_count', 'usage_limit', 'minimum_purchase',
        'valid_from', 'valid_until',
    ]
    list_filter = ['is_active', 'discount_type']
    search_fields = ['code']
    readonly_fields = ['usage_count', 'created_at', 'updated_at']
    fieldsets = (
        ('Código', {'fields': ('code', 'is_active')}),
        ('Descuento', {'fields': ('discount_type', 'discount_value', 'minimum_purchase')}),
        ('Vigencia', {'fields': ('valid_from', 'valid_until')}),
        ('Usos', {'fields': ('usage_limit', 'usage_count')}),
        ('Metadatos', {'fields': ('created_at', 'updated_at')}),
    )
