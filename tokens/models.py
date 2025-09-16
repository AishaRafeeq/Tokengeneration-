from django.db import models
from django.utils import timezone
from django.conf import settings
from django.db.models import Max
from users.models import Category
from django.utils.crypto import get_random_string
import logging


class Token(models.Model):
    STATUS_CHOICES = [
        ('waiting', 'Waiting'),
        ('called', 'Called'),
        ('inprogress', 'In Progress'),
        ('completed', 'Completed'),
    ]

    token_id = models.CharField(max_length=32, unique=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    queue_position = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')
    issued_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )

    def save(self, *args, **kwargs):
        is_new = self.pk is None

        if is_new:
            # Generate token_id automatically
            last_token = Token.objects.filter(category=self.category).order_by('-id').first()
            next_id = 1 if not last_token else int(last_token.token_id[1:]) + 1
            prefix = self.category.name[0].upper()
            self.token_id = f"{prefix}{next_id:03d}"

            # Assign queue position
            max_position = Token.objects.filter(
                category=self.category, status='waiting'
            ).aggregate(Max('queue_position'))['queue_position__max']
            self.queue_position = 1 if max_position is None else max_position + 1

        super().save(*args, **kwargs)

        # Auto-generate QR code only if it doesn't exist
        if is_new and not hasattr(self, "qr_code"):
            try:
                from .utils import generate_qr_code
                qr_settings = QRSettings.objects.first()
                qr_data, checksum, file_path = generate_qr_code(self, qr_settings)
                QRCode.objects.create(
                    token=self,
                    category=self.category,
                    expires_at=qr_data["expires_at"],
                    checksum=checksum,
                    payload=qr_data,
                    image=file_path,
                    format=qr_settings.default_format if qr_settings else 'PNG',
                    created_by=self.issued_by
                )
            except Exception as e:
                logging.exception("QR generation failed for token %s", self.token_id)
                # Optionally: continue without QR or raise a custom exception

    def __str__(self):
        return f"{self.token_id} ({self.category}) - {self.status}"


class QRSettings(models.Model):
    ERROR_CORRECTION_CHOICES = [
        ('L', 'L (7%)'),
        ('M', 'M (15%)'),
        ('Q', 'Q (25%)'),
        ('H', 'H (30%)')
    ]
    base_url = models.URLField(default='http://localhost:3000/token-status/')
    default_size = models.IntegerField(default=10)
    default_border = models.IntegerField(default=4)
    error_correction = models.CharField(
        max_length=1, choices=ERROR_CORRECTION_CHOICES, default='M'
    )
    default_expiry_hours = models.IntegerField(default=24)
    default_format = models.CharField(max_length=10, default='PNG')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"QR Settings (updated {self.updated_at.isoformat()})"


class QRCode(models.Model):
    token = models.OneToOneField(Token, on_delete=models.CASCADE, related_name="qr_code")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    generated_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    checksum = models.CharField(max_length=128)
    payload = models.JSONField(default=dict)
    image = models.ImageField(upload_to='qrcodes/', blank=True, null=True)
    format = models.CharField(max_length=10, default='PNG')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    data = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=(('VALID', 'VALID'), ('EXPIRED', 'EXPIRED'), ('INVALID', 'INVALID')),
        default='VALID'
    )

    def __str__(self):
        return f"QR for {self.token.token_id} ({self.checksum[:8]})"


class QRScan(models.Model):
    qr = models.ForeignKey(QRCode, on_delete=models.CASCADE, related_name='scans')
    scanned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    scan_time = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    device_type = models.CharField(max_length=50, blank=True)
    verification_status = models.CharField(
        max_length=32,
        choices=(('SUCCESS', 'SUCCESS'), ('FAILED', 'FAILED')),
        default='SUCCESS'
    )
    details = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"Scan {self.id}: {self.qr.token.token_id} @ {self.scan_time.isoformat()}"


class QRTemplate(models.Model):
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=7, default="#000000")
    # Extend with more styling options (logo, background, etc.)

    def __str__(self):
        return self.name


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('SCAN', 'Scan'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model = models.CharField(max_length=100)
    object_id = models.CharField(max_length=100, blank=True, null=True)
    details = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    def __str__(self):
        return f"{self.user} {self.action} {self.model} ({self.timestamp})"
