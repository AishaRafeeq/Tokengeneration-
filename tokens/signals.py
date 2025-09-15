from django.db.models.signals import post_save
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Token, QRScan

@receiver(post_save, sender=Token)
def notify_token_status(sender, instance, created, **kwargs):
    layer = get_channel_layer()
    data = {
        "type": "send_notification",
        "message": {
            "event": "token_updated",
            "token_id": instance.token_id,
            "status": instance.status,
            "queue_position": instance.queue_position
        }
    }
    async_to_sync(layer.group_send)("notifications", data)

@receiver(post_save, sender=QRScan)
def notify_qr_scan(sender, instance, created, **kwargs):
    if created:
        layer = get_channel_layer()
        data = {
            "type": "send_notification",
            "message": {
                "event": "qr_scanned",
                "token_id": instance.qr.token.token_id,
                "scanned_by": instance.scanned_by.username if instance.scanned_by else "Guest",
                "time": str(instance.scan_time)
            }
        }
        async_to_sync(layer.group_send)("notifications", data)
