from django.contrib.auth.models import AbstractUser
from django.db import models

class Category(models.Model):
    name = models.CharField(max_length=50, unique=True)
    color = models.CharField(max_length=7, default="#000000", help_text="Hex color for QR code (e.g. #FF0000)")

    def __str__(self):
        return self.name


class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('staff', 'Staff'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='staff')
    categories = models.ManyToManyField(Category, blank=True, related_name='staff_members')

    # QR permissions
    can_scan_qr = models.BooleanField(default=False)
    can_generate_qr = models.BooleanField(default=False)
    can_view_analytics = models.BooleanField(default=False)
    can_verify_qr = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.username} ({self.role})"

    @property
    def full_name(self):
        """Return the full name of the user."""
        return f"{self.first_name} {self.last_name}".strip()
