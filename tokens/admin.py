from django.contrib import admin
from django.db import models
from .models import Token, QRCode, QRScan, QRSettings
from .utils import generate_qr_code
from .models import QRSettings as QRSettingsModel

@admin.register(Token)
class TokenAdmin(admin.ModelAdmin):
    list_display = ['token_id', 'category', 'queue_position', 'status', 'issued_at', 'updated_at']
    list_filter = ['status', 'category']
    search_fields = ['token_id']
    readonly_fields = ['token_id', 'queue_position']  # auto fields read-only

    def save_model(self, request, obj, form, change):
        # Set issued_by automatically to current admin user
        if not obj.issued_by:
            obj.issued_by = request.user

        # Auto-generate token_id if not provided
        if not obj.token_id:
            last_token = Token.objects.filter(category=obj.category).order_by('-id').first()
            next_id = 1 if not last_token else int(last_token.token_id[1:]) + 1
            prefix = obj.category.name[0].upper()
            obj.token_id = f"{prefix}{next_id:03d}"

        # Auto-assign queue position
        if not obj.queue_position:
            max_position = Token.objects.filter(
                category=obj.category,
                status='waiting'
            ).aggregate(models.Max('queue_position'))['queue_position__max']
            obj.queue_position = 1 if max_position is None else max_position + 1

        super().save_model(request, obj, form, change)

        # Auto-generate QRCode if it does not exist
        if not QRCode.objects.filter(token=obj).exists():
            qr_settings = QRSettingsModel.objects.first()
            qr_data, checksum, file = generate_qr_code(obj, qr_settings)

            format_value = qr_settings.default_format if qr_settings else 'PNG'

            # Properly serialize payload (no model instances)
            payload_data = {
                "token_id": obj.token_id,
                "category_id": obj.category.id,
                "category_name": obj.category.name,
                "category_color": getattr(obj.category, 'color', None),
                "expires_at": qr_data.get("expires_at"),
            }

            QRCode.objects.create(
                token=obj,
                category=obj.category,  # ForeignKey assignment is safe
                expires_at=qr_data["expires_at"],
                checksum=checksum,
                payload=payload_data,
                image=file,
                format=format_value,
                created_by=obj.issued_by
            )


@admin.register(QRCode)
class QRCodeAdmin(admin.ModelAdmin):
    list_display = ['token', 'category', 'generated_at', 'expires_at', 'format']
    search_fields = ['token__token_id', 'checksum']
    list_filter = ['format', 'category']


@admin.register(QRScan)
class QRScanAdmin(admin.ModelAdmin):
    list_display = ['qr', 'scanned_by', 'scan_time', 'device_type', 'verification_status']
    list_filter = ['verification_status', 'device_type']
    search_fields = ['qr__token__token_id']


@admin.register(QRSettings)
class QRSettingsAdmin(admin.ModelAdmin):
    list_display = ['base_url', 'default_size', 'error_correction', 'default_expiry_hours', 'updated_at']
