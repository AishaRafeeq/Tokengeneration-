from django.db import models

class SidebarSection(models.Model):
    title = models.CharField(max_length=100)
    visible_to_admin = models.BooleanField(default=True)
    visible_to_staff = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.title


class SidebarItem(models.Model):
    section = models.ForeignKey(SidebarSection, related_name='items', on_delete=models.CASCADE)
    title = models.CharField(max_length=100)
    url = models.CharField(max_length=200)
    visible_to_admin = models.BooleanField(default=True)
    visible_to_staff = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.title
