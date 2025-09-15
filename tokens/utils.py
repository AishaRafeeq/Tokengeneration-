import hashlib
from io import BytesIO
from django.core.files.base import ContentFile
from django.utils import timezone
from datetime import timedelta
from .models import QRSettings
import qrcode
import os
from django.conf import settings

def generate_qr_code(token_obj, qr_settings=None):
    # Use defaults if qr_settings is None
    default_format = getattr(qr_settings, 'default_format', 'PNG')
    default_size = getattr(qr_settings, 'default_size', 300)
    error_correction = getattr(qr_settings, 'error_correction', 'M')
    expiry_hours = getattr(qr_settings, 'default_expiry_hours', 24)
    base_url = getattr(qr_settings, 'base_url', 'https://example.com/')

    expires_at = timezone.now() + timedelta(hours=expiry_hours)

    payload = {
        "tokenId": token_obj.token_id,
        "category_id": token_obj.category.id,
        "category_name": token_obj.category.name,
        "category_color": getattr(token_obj.category, 'color', None),
        "timestamp": timezone.now().isoformat(),
        "queuePosition": token_obj.queue_position,
        "status": token_obj.status,
        "expires_at": expires_at.isoformat(),
    }

    checksum = hashlib.sha256(str(payload).encode("utf-8")).hexdigest()
    payload["checksum"] = checksum

    qr_data = {
        "token_id": token_obj.token_id,
        "category_id": token_obj.category.id,
        "category_name": token_obj.category.name,
        "category_color": getattr(token_obj.category, 'color', None),
        "expires_at": expires_at.isoformat(),  # <-- ADD THIS LINE
    }

    # Get color from category, fallback to black
    fill_color = getattr(token_obj.category, 'color', '#000000')

    qr = qrcode.QRCode(
        version=1,
        error_correction=getattr(qrcode.constants, f"ERROR_CORRECT_{error_correction}") if qr_settings else qrcode.constants.ERROR_CORRECT_M,
        box_size=default_size,
        border=qr_settings.default_border if qr_settings else 4,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color=fill_color, back_color="white")

    buffer = BytesIO()
    img.save(buffer, format=default_format)
    file = ContentFile(buffer.getvalue(), name=f"qrcode_{token_obj.token_id}.{(default_format).lower()}")

    filename = f"{token_obj.token_id}.png"
    qr_dir = os.path.join(settings.MEDIA_ROOT, 'qrcodes')
    os.makedirs(qr_dir, exist_ok=True)  # Ensure directory exists
    file_path = os.path.join(qr_dir, filename)
    img.save(file_path, format='PNG')
    # Return a relative path for ImageField
    return qr_data, checksum, f"qrcodes/{filename}"
