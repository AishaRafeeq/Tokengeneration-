from django.contrib import admin
from .models import SidebarSection, SidebarItem

class SidebarItemInline(admin.TabularInline):
    model = SidebarItem
    extra = 1

@admin.register(SidebarSection)
class SidebarSectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'visible_to_admin', 'visible_to_staff', 'order')
    inlines = [SidebarItemInline]

@admin.register(SidebarItem)
class SidebarItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'section', 'url', 'visible_to_admin', 'visible_to_staff', 'order')
