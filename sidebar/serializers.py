from rest_framework import serializers
from .models import SidebarSection, SidebarItem

class SidebarItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SidebarItem
        fields = ['id', 'title', 'url', 'order']

class SidebarSectionSerializer(serializers.ModelSerializer):
    items = SidebarItemSerializer(many=True, read_only=True)

    class Meta:
        model = SidebarSection
        fields = ['id', 'title', 'order', 'items']
