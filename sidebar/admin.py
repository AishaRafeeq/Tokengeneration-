from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from import_export import resources
from .models import SidebarSection, SidebarItem

# -------------------------------
# Resources
# -------------------------------
class SidebarSectionResource(resources.ModelResource):
    class Meta:
        model = SidebarSection
        import_id_fields = ('id',)
        fields = ('id', 'title', 'visible_to_admin', 'visible_to_staff', 'order')

class SidebarItemResource(resources.ModelResource):
    class Meta:
        model = SidebarItem
        import_id_fields = ('id',)
        fields = ('id', 'title', 'section', 'url', 'visible_to_admin', 'visible_to_staff', 'order')


# -------------------------------
# Admin
# -------------------------------
class SidebarItemInline(admin.TabularInline):
    model = SidebarItem
    extra = 1


@admin.register(SidebarSection)
class SidebarSectionAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    resource_class = SidebarSectionResource
    list_display = ('title', 'visible_to_admin', 'visible_to_staff', 'order')
    inlines = [SidebarItemInline]


@admin.register(SidebarItem)
class SidebarItemAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    resource_class = SidebarItemResource
    list_display = ('title', 'section', 'url', 'visible_to_admin', 'visible_to_staff', 'order')
