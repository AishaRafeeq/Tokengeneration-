from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Category

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'role', 'is_active']
    list_filter = ['role', 'categories']
    filter_horizontal = ['categories']

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Permissions', {
            'fields': (
                'role', 'can_scan_qr', 'can_generate_qr', 'can_view_analytics', 'can_verify_qr', 'categories'
            ),
        }),
    )
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'color_display']

    def color_display(self, obj):
        return f'<div style="width:30px;height:20px;background:{obj.color};"></div>'
    color_display.allow_tags = True
    color_display.short_description = 'Color'
