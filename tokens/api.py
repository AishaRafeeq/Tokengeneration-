from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .models import Token, QRCode, QRScan
from users.models import Category
from users.serializers import CategorySerializer
from django.utils import timezone
from .serializers import TokenSerializer  # You need to create/adjust this serializer

class QueueViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def live(self, request):
        """
        Live queue monitoring: List all tokens by category and status, with QR code status.
        """
        data = []
        for category in Category.objects.all():
            tokens = Token.objects.filter(category=category, status='waiting').order_by('queue_position')
            tokens_data = []
            for token in tokens:
                qr_status = "generated" if hasattr(token, "qr_code") else "pending"
                tokens_data.append({
                    "token_id": token.token_id,
                    "queue_position": token.queue_position,
                    "status": token.status,
                    "issued_at": token.issued_at,
                    "qr_status": qr_status,
                })
            data.append({
                "category": CategorySerializer(category).data,
                "tokens": tokens_data,
            })
        return Response(data)

    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """
        Token status overview with QR verification info.
        """
        try:
            token = Token.objects.get(pk=pk)
        except Token.DoesNotExist:
            return Response({"detail": "Token not found."}, status=404)
        qr_code = getattr(token, "qr_code", None)
        last_scan = None
        verification_status = None
        if qr_code:
            last_scan = qr_code.scans.order_by('-scan_time').first()
            verification_status = last_scan.verification_status if last_scan else None
        return Response({
            "token_id": token.token_id,
            "status": token.status,
            "category": token.category.name,
            "issued_at": token.issued_at,
            "qr_code": {
                "exists": qr_code is not None,
                "expires_at": getattr(qr_code, "expires_at", None),
                "last_scan": last_scan.scan_time if last_scan else None,
                "verification_status": verification_status,
            }
        })

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def emergency(self, request):
        """
        Emergency queue control: pause, resume, or clear queue.
        POST {"action": "pause"|"resume"|"clear", "category_id": optional}
        """
        action_type = request.data.get("action")
        category_id = request.data.get("category_id")
        if category_id:
            try:
                category = Category.objects.get(pk=category_id)
            except Category.DoesNotExist:
                return Response({"detail": "Category not found."}, status=404)
            tokens = Token.objects.filter(category=category)
        else:
            tokens = Token.objects.all()

        if action_type == "pause":
            tokens.update(status="waiting")
            return Response({"detail": "Queue paused."})
        elif action_type == "resume":
            tokens.filter(status="waiting").update(status="inprogress")
            return Response({"detail": "Queue resumed."})
        elif action_type == "clear":
            tokens.delete()
            return Response({"detail": "Queue cleared."})
        else:
            return Response({"detail": "Invalid action."}, status=400)

    @action(detail=False, methods=['get'])
    def scanner_status(self, request):
        """
        QR code scanner integration status: last scan and verification for each token.
        """
        tokens = Token.objects.all()
        data = []
        for token in tokens:
            qr_code = getattr(token, "qr_code", None)
            last_scan = qr_code.scans.order_by('-scan_time').first() if qr_code else None
            data.append({
                "token_id": token.token_id,
                "status": token.status,
                "category": token.category.name,
                "last_scan": last_scan.scan_time if last_scan else None,
                "verification_status": last_scan.verification_status if last_scan else None,
            })
        return Response(data)