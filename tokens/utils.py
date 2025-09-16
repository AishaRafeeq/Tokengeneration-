from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from io import BytesIO
import qrcode
import hashlib
from django.utils import timezone
from datetime import timedelta
from PIL import Image

def generate_qr_code(token_obj, qr_settings=None):
    # Sensible defaults
    default_format = getattr(qr_settings, 'default_format', 'PNG')
    default_size = getattr(qr_settings, 'default_size', 10)
    error_correction = getattr(qr_settings, 'error_correction', 'M')
    expiry_hours = getattr(qr_settings, 'default_expiry_hours', 24)
    border = getattr(qr_settings, 'default_border', 4)
    base_url = getattr(qr_settings, 'base_url', 'https://example.com/')

    expires_at = timezone.now() + timedelta(hours=expiry_hours)

    payload = {
        "tokenId": token_obj.token_id,
        "category_id": token_obj.category.id,
        "category_name": token_obj.category.name,
        "timestamp": timezone.now().isoformat(),
        "queuePosition": token_obj.queue_position,
        "status": token_obj.status,
        "expires_at": expires_at.isoformat(),
    }

    checksum = hashlib.sha256(str(payload).encode("utf-8")).hexdigest()

    qr_data = {
        "token_id": token_obj.token_id,
        "category_id": token_obj.category.id,
        "category_name": token_obj.category.name,
        "category_color": getattr(token_obj.category, 'color', None),
        "expires_at": expires_at.isoformat(),
    }

    fill_color = getattr(token_obj.category, 'color', '#000000')

    qr = qrcode.QRCode(
        version=1,
        error_correction=getattr(qrcode.constants, f"ERROR_CORRECT_{error_correction}") if qr_settings else qrcode.constants.ERROR_CORRECT_M,
        box_size=int(default_size),
        border=int(border),
    )
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color=fill_color, back_color="white")

    buffer = BytesIO()
    img.save(buffer, format=default_format)
    buffer.seek(0)

    filename = f"qrcodes/qrcode_{token_obj.token_id}.{default_format.lower()}"
    content = ContentFile(buffer.read())
    saved_path = default_storage.save(filename, content)

    return qr_data, checksum, saved_path  # saved_path is 'qrcodes/qrcode_A001.png'

def generate_colored_qr_code(data, color="#007BFF"):
    qr_img = qrcode.make(data)
    qr_img = qr_img.convert("RGBA")
    border_size = 20
    bg = Image.new("RGBA", (qr_img.width + border_size*2, qr_img.height + border_size*2), color)
    bg.paste(qr_img, (border_size, border_size))
    buffer = BytesIO()
    bg.save(buffer, format="PNG")
    return buffer
