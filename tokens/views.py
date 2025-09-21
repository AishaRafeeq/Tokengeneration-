from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.parsers import MultiPartParser
from django.utils import timezone
from django.db.models import Max
from datetime import time 

from django.http import FileResponse
from django.conf import settings
from django.db.models import Count
from datetime import date, timedelta
from django.utils.crypto import get_random_string
from django.core.files.base import ContentFile

from .models import Token, QRCode, QRScan, QRSettings, QRTemplate, AuditLog
from .serializers import (
    TokenSerializer,
    QRCodeSerializer,
    QRScanSerializer,
    QRSettingsSerializer,
    QRTemplateSerializer,
    AuditLogSerializer,
    ScanActivityReportSerializer,
    VerificationLogSerializer,
)
from users.models import Category
from .utils import generate_colored_qr_code


def is_within_generation_time():
    settings = QRSettings.objects.first()
    now = timezone.localtime()
    start = settings.generation_start_time
    end = settings.generation_end_time
    print("DEBUG:", "Now:", now.time(), "Start:", start, "End:", end)
    return start <= now.time() <= end

class TokenViewSet(viewsets.ModelViewSet):
    queryset = Token.objects.all().order_by("queue_position")
    serializer_class = TokenSerializer
    permission_classes = [AllowAny]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["token_id", "category__name", "status"]
    ordering_fields = ["issued_at", "queue_position"]
    lookup_field = 'token_id'

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset().filter(status__in=["waiting", "called"]).order_by("queue_position")
      
        qs = qs.exclude(source="manual")
       
        if hasattr(user, "role") and user.role == "staff":
            staff_categories = getattr(user, "categories", None)
            if staff_categories is not None:
                qs = qs.filter(category__in=staff_categories.all())
            else:
                qs = qs.none()
        return qs

    @action(detail=False, methods=["get"])
    def active(self, request):
      tokens = self.get_queryset().filter(status__in=["waiting", "called"]).order_by("queue_position")
      serializer = TokenSerializer(tokens, many=True, context={"request": request})
      return Response(serializer.data)


    @action(detail=False, methods=["post"])
    def call_next(self, request):
        user = request.user
        qs = self.get_queryset()
        # Complete the current "called" token, if any
        current_token = qs.filter(status="called").first()
        if current_token:
            current_token.status = "completed"
            current_token.save()
        # Call only the next "waiting" token
        next_token = qs.filter(status="waiting").order_by("queue_position").first()
        if not next_token:
            return Response({"detail": "No waiting tokens available"}, status=404)
        next_token.status = "called"
        next_token.save()
        return Response(TokenSerializer(next_token).data)

    @action(detail=True, methods=["post"])
    def complete(self, request, token_id=None):
        try:
            token = self.get_object()
        except Token.DoesNotExist:
            return Response({"error": "Token not found"}, status=404)
        token.status = "completed"
        token.save()
    # Automatically call the next waiting token (if any)
        next_token = self.get_queryset().filter(status="waiting").order_by("queue_position").first()
        if next_token:
            next_token.status = "called"
            next_token.save()
            return Response({
                "success": True,
                "completed_token_id": token.token_id,
                "next_token_id": next_token.token_id,
                "next_status": next_token.status,
            })
        else:
            return Response({
                "success": True,
                "completed_token_id": token.token_id,
                "next_token_id": None,
                "next_status": None,
            })

    @action(detail=False, methods=["post"])
    def manual_call(self, request):
        user = request.user
        token_id = request.data.get("token_id")
        if not token_id:
            return Response({"detail": "token_id is required"}, status=400)

        # Only allow staff to call for their assigned category
        if hasattr(user, "role") and user.role == "staff":
            staff_categories = getattr(user, "categories", None)
            if not staff_categories or staff_categories.count() == 0:
                return Response({"detail": "You are not assigned to any category."}, status=403)
            if staff_categories.count() > 1:
                return Response({"detail": "You are assigned to multiple categories. Please contact admin."}, status=400)
            category = staff_categories.first()
            category_id = category.id
        elif hasattr(user, "role") and user.role == "admin":
            category_id = request.data.get("category_id")
            if not category_id:
                return Response({"detail": "category_id is required for admin"}, status=400)
            try:
                category = Category.objects.get(id=category_id)
            except Category.DoesNotExist:
                return Response({"detail": "Invalid category"}, status=400)
        else:
            return Response({"detail": "Unauthorized"}, status=403)

        # For manual tokens (token_id starts with "MAN"), avoid duplicate calling and do NOT generate QR
        if token_id.startswith("MAN"):
            existing_token = Token.objects.filter(token_id=token_id, category_id=category_id, source="manual").exclude(status="completed").first()
            if existing_token:
                return Response({"detail": "This manual token is already active or called."}, status=400)
            # Find the current max queue_position for this category
            max_position = Token.objects.filter(category_id=category_id).aggregate(Max('queue_position'))['queue_position__max'] or 0
            # Create manual token at the end of the queue
            token = Token.objects.create(
                token_id=token_id,
                category_id=category_id,
                status="called",
                issued_at=timezone.now(),
                source="manual",
                queue_position=max_position + 1
            )
            return Response({
                "token_id": token.token_id,
                "status": token.status,
                "category": {
                    "id": token.category.id,
                    "name": token.category.name,
                },
                "queue_position": token.queue_position,
                "source": token.source,
            })
        else:
            # For non-manual tokens, only call if in waiting status
            token = Token.objects.filter(token_id=token_id, category_id=category_id).first()
            if not token:
                return Response({"detail": "Token not found."}, status=404)
            if token.status != "waiting":
                return Response({"detail": "Token is not in waiting status."}, status=400)
            token.status = "called"
            token.save()
            return Response(TokenSerializer(token).data)

    @action(detail=False, methods=["post"], permission_classes=[AllowAny])
    def admin_generate(self, request):
        if not is_within_generation_time():
            return Response({"error": "Token generation is only allowed between configured hours."}, status=403)
        category_id = request.data.get("category")
        status = request.data.get("status", "waiting")
        issued_at = request.data.get("issued_at", timezone.now())
        if not category_id:
            return Response({"detail": "category is required"}, status=400)
        try:
            category = Category.objects.get(id=category_id)
        except Category.DoesNotExist:
            return Response({"detail": "Invalid category"}, status=400)
        max_position = Token.objects.filter(category_id=category_id).aggregate(Max('queue_position'))['queue_position__max'] or 0
        token = Token.objects.create(
            category=category,
            status=status,
            issued_at=issued_at,
            created_by=request.user if request.user.is_authenticated else None,
            source="admin",
            queue_position=max_position + 1,
        )
        expires_at = timezone.now() + timedelta(hours=24)
        qr_data = token.token_id  
        color = category.color if hasattr(category, "color") else "#007BFF"
        qr_buffer = generate_colored_qr_code(qr_data, color)
        file_name = f"qr_{token.token_id}.png"
        qr_code = QRCode.objects.create(
            token=token,
            category=category,
            expires_at=expires_at,
            data=qr_data,
        )
        qr_code.image.save(file_name, ContentFile(qr_buffer.getvalue()), save=True)
        # --- FIX: Add queue_position and category to qr_code response ---
        return Response({
            "token": {
                "token_id": token.token_id,
                "status": token.status,
                "category": {
                    "id": category.id,
                    "name": category.name,
                },
                "queue_position": token.queue_position,
            },
            "qr_code": {
                "image": request.build_absolute_uri(qr_code.image.url) if qr_code.image else None,
                "data": qr_code.data,
                "category": {
                    "id": category.id,
                    "name": category.name,
                },
                "queue_position": token.queue_position,
            },
        }, status=201)

    @action(detail=False, methods=['post'], url_path='public-create')
    def public_create(self, request):
        if not is_within_generation_time():
            return Response({"error": "Token generation is only allowed between configured hours."}, status=403)
        category_id = request.data.get("category")
        if not category_id:
            return Response({"error": "Category required"}, status=400)
        try:
            category = Category.objects.get(id=category_id)
        except Category.DoesNotExist:
            return Response({"error": "Invalid category"}, status=400)
        token = Token.objects.create(category=category, status="waiting")
        expires_at = timezone.now() + timedelta(hours=24)

        # Generate QR code with category color and token_id as data
        qr_data = token.token_id
        color = category.color if hasattr(category, "color") else "#007BFF"
        qr_buffer = generate_colored_qr_code(qr_data, color)
        file_name = f"qr_{token.token_id}.png"

        qr_code = QRCode.objects.create(
            token=token,
            category=category,
            expires_at=expires_at,
            data=qr_data,
        )
        qr_code.image.save(file_name, ContentFile(qr_buffer.getvalue()), save=True)

        return Response({
            "token": {
                "token_id": token.token_id,
                "status": token.status,
                "category": {
                    "id": category.id,
                    "name": category.name,
                },
                "queue_position": token.queue_position,
            },
            "qr_code": {
                "image": request.build_absolute_uri(qr_code.image.url) if qr_code.image else None,
                "data": qr_code.data,
            },
        }, status=201)

    @action(detail=False, methods=['get'], url_path='public/(?P<token_id>[^/.]+)')
    def public(self, request, token_id=None):
        try:
            token = Token.objects.get(token_id=token_id)
        except Token.DoesNotExist:
            return Response({"detail": "Invalid QR Code"}, status=404)
        qr_code = QRCode.objects.filter(token=token).order_by('-id').first()
        return Response({
            "token_id": token.token_id,
            "status": token.status,
            "category": {
                "id": token.category.id,
                "name": token.category.name,
            },
            "queue_position": token.queue_position,
            "qr_image": request.build_absolute_uri(qr_code.image.url) if qr_code and qr_code.image else None,
        })

    @action(detail=False, methods=["get"])
    def admin_tokens(self, request):
        tokens = self.get_queryset().filter(source="admin").exclude(status="completed").order_by("-issued_at")
        serializer = self.get_serializer(tokens, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="admin-bulk-generate")
    def admin_bulk_generate(self, request):
        category_id = request.data.get("category")
        count = int(request.data.get("count", 1))
        status_val = request.data.get("status", "waiting")
        if not category_id or count < 1:
            return Response({"detail": "category and count required"}, status=400)
        try:
            category = Category.objects.get(id=category_id)
        except Category.DoesNotExist:
            return Response({"detail": "Invalid category"}, status=400)
        created_tokens = []
        max_position = Token.objects.filter(category_id=category_id).aggregate(Max('queue_position'))['queue_position__max'] or 0
        for i in range(count):
            token = Token.objects.create(
                category=category,
                status=status_val,
                issued_at=timezone.now(),
                created_by=request.user if request.user.is_authenticated else None,
                source="admin",
                queue_position=max_position + i + 1,
            )
            expires_at = timezone.now() + timedelta(hours=24)
            qr_data = token.token_id
            color = category.color if hasattr(category, "color") else "#007BFF"
            qr_buffer = generate_colored_qr_code(qr_data, color)
            file_name = f"qr_{token.token_id}.png"
            qr_code = QRCode.objects.create(
                token=token,
                category=category,
                expires_at=expires_at,
                data=qr_data,
            )
            qr_code.image.save(file_name, ContentFile(qr_buffer.getvalue()), save=True)
            created_tokens.append({
                "token_id": token.token_id,
                "status": token.status,
                "category": {
                    "id": category.id,
                    "name": category.name,
                },
                "queue_position": token.queue_position,
                "qr_image": request.build_absolute_uri(qr_code.image.url) if qr_code.image else None,
            })
        return Response({"created": created_tokens, "count": len(created_tokens)}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"])
    def live_queue(self, request):
        # Fetch all tokens with status "waiting"
        tokens = Token.objects.filter(status="waiting").order_by("queue_position")
        # Group tokens by category
        categories = {}
        for token in tokens:
            cat_id = token.category.id
            if cat_id not in categories:
                categories[cat_id] = {
                    "category": {
                        "id": token.category.id,
                        "name": token.category.name,
                    },
                    "tokens": [],
                }
            qr_code = QRCode.objects.filter(token=token).order_by('-id').first()
            categories[cat_id]["tokens"].append({
                "token_id": token.token_id,
                "status": token.status,
                "queue_position": token.queue_position,
                "issued_at": token.issued_at,
                "qr_image": request.build_absolute_uri(qr_code.image.url) if qr_code and qr_code.image else None,
            })
        return Response({"live_queue": list(categories.values())})

        from django.utils import timezone

    @action(detail=False, methods=["post"], url_path="verify-qr")
    def verify_qr(self, request, *args, **kwargs):
      token_id = request.data.get("token_id")
      qr_code_id = request.data.get("qr_code_id")
      user = request.user
      qr_code = None
      token = None
      verified = False

      if token_id:
        try:
            token = Token.objects.get(token_id=token_id)
        except Token.DoesNotExist:
            # ❌ Log failed scan
            QRScan.objects.create(
                qr=None,  # Correct field name
                scanned_by=user,
                verification_status="FAILED",
                scan_count=1
            )
            return Response({"verified": False, "detail": "Token not found."}, status=404)

        qr_code = QRCode.objects.filter(token=token).order_by("-id").first()
        verified = token.status in ["waiting", "called"]

      elif qr_code_id:
        try:
            qr_code = QRCode.objects.get(id=qr_code_id)
            token = qr_code.token
            verified = token.status in ["waiting", "called"]
        except QRCode.DoesNotExist:
            # ❌ Log failed scan
            QRScan.objects.create(
                qr=None,  # Correct field name
                scanned_by=user,
                verification_status="FAILED",
                scan_count=1
            )
            return Response({"verified": False, "detail": "QR code not found."}, status=404)

      else:
        return Response({"verified": False, "detail": "token_id or qr_code_id required."}, status=400)

      verification_status = "SUCCESS" if verified else "FAILED"

    # ✅ Log scan result with scan_count increment
      scan, created = QRScan.objects.get_or_create(
        qr=qr_code,  # Correct field name
        scanned_by=user,
        defaults={"verification_status": verification_status, "scan_count": 1}
      )
      if not created:
         scan.scan_count += 1
         scan.verification_status = verification_status  # Update latest status
         scan.scan_time = timezone.now()  # Update timestamp
         scan.save()

      return Response({
        "token_id": token.token_id,
        "verified": verified,
        "verification_status": verification_status,
        "qr_image": request.build_absolute_uri(qr_code.image.url) if qr_code and qr_code.image else None,
        "status": token.status,
        "category": {
            "id": token.category.id,
            "name": token.category.name,
        }
    
    })



    @action(detail=False, methods=["get", "post"], url_path="qr-settings")
    def qr_settings(self, request):
        from .models import QRSettings
        if request.method == "GET":
            settings = QRSettings.objects.first()
            if not settings:
                return Response({"error": "No settings found"}, status=404)
            return Response({
                "size": settings.size,
                "border": settings.border,
                "error_correction": settings.error_correction,
                "expiry_hours": settings.expiry_hours,
                "generation_start_time": settings.generation_start_time,
                "generation_end_time": settings.generation_end_time,
                "daily_reset": settings.daily_reset,
            })
        elif request.method == "POST":
            data = request.data
            settings, _ = QRSettings.objects.get_or_create(pk=1)
            settings.size = int(data.get("size", settings.size))
            settings.border = int(data.get("border", settings.border))
            settings.error_correction = data.get("error_correction", settings.error_correction)
            settings.expiry_hours = int(data.get("expiry_hours", settings.expiry_hours))
            if "generation_start_time" in data:
                val = data["generation_start_time"]
                if isinstance(val, str):
                    parts = val.split(":")
                    h = int(parts[0])
                    m = int(parts[1])
                    s = int(parts[2]) if len(parts) > 2 else 0
                    settings.generation_start_time = time(hour=h, minute=m, second=s)
                else:
                    settings.generation_start_time = val
            if "generation_end_time" in data:
                val = data["generation_end_time"]
                if isinstance(val, str):
                    parts = val.split(":")
                    h = int(parts[0])
                    m = int(parts[1])
                    s = int(parts[2]) if len(parts) > 2 else 0
                    settings.generation_end_time = time(hour=h, minute=m, second=s)
                else:
                    settings.generation_end_time = val
            if "daily_reset" in data:
                settings.daily_reset = data["daily_reset"]
            settings.save()
            return Response({"success": True, "settings": {
                "size": settings.size,
                "border": settings.border,
                "error_correction": settings.error_correction,
                "expiry_hours": settings.expiry_hours,
                "generation_start_time": settings.generation_start_time,
                "generation_end_time": settings.generation_end_time,
                "daily_reset": settings.daily_reset,
            }})

    @action(detail=False, methods=["get"], url_path="staff-queue")
    def staff_queue(self, request):
        user = request.user
        if hasattr(user, "role") and user.role == "staff":
            staff_categories = getattr(user, "categories", None)
            if staff_categories:
                tokens = Token.objects.filter(category__in=staff_categories.all(), status="waiting").order_by("queue_position")
            else:
                tokens = Token.objects.none()
        else:
            tokens = Token.objects.none()
        # Group tokens by category
        categories = {}
        for token in tokens:
            cat_id = token.category.id
            if cat_id not in categories:
                categories[cat_id] = {
                    "category": {
                        "id": token.category.id,
                        "name": token.category.name,
                    },
                    "tokens": [],
                }
            categories[cat_id]["tokens"].append({
                "token_id": token.token_id,
                "status": token.status,
                "queue_position": token.queue_position,
                "issued_at": token.issued_at,
            })
        return Response({"staff_queue": list(categories.values())})

    @action(detail=False, methods=["post"], url_path="staff-call-next")
    def staff_call_next(self, request):
        """
        Staff: Complete current called token and call next waiting token (one at a time).
        """
        user = request.user
        # Only allow staff
        if not (hasattr(user, "role") and user.role == "staff"):
            return Response({"detail": "Only staff can call next."}, status=403)

        staff_categories = getattr(user, "categories", None)
        if not staff_categories or staff_categories.count() == 0:
            return Response({"detail": "You are not assigned to any category."}, status=403)

        # Complete the current called token (if any)
        current_token = Token.objects.filter(
            category__in=staff_categories.all(),
            status="called"
        ).order_by("queue_position").first()
        if current_token:
            current_token.status = "completed"
            current_token.save(update_fields=["status"])

        # Call the next waiting token
        next_token = Token.objects.filter(
            category__in=staff_categories.all(),
            status="waiting"
        ).order_by("queue_position").first()
        if not next_token:
            return Response({"detail": "No waiting tokens available."}, status=status.HTTP_200_OK)

        next_token.status = "called"
        next_token.save(update_fields=["status"])

        return Response({
            "token_id": next_token.token_id,
            "category": next_token.category.id if next_token.category else None,
            "category_name": next_token.category.name if next_token.category else None,
            "status": next_token.status,
        }, status=status.HTTP_200_OK)

class QRCodeViewSet(viewsets.ModelViewSet):
    queryset = QRCode.objects.all().order_by("-generated_at")
    serializer_class = QRCodeSerializer
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["token__token_id", "category", "checksum"]
    ordering_fields = ["generated_at", "expires_at"]

    @action(detail=False, methods=["post"])
    def generate(self, request):
        serializer = QRCodeSerializer(data=request.data)
        if serializer.is_valid():
            qr = serializer.save()
            return Response(QRCodeSerializer(qr).data, status=201)
        return Response(serializer.errors, status=400)
    @action(detail=True, methods=["get"], url_path="public", permission_classes=[AllowAny])
    def public(self, request, token_id=None):
        try:
            token = self.get_queryset().get(token_id=token_id)
        except Token.DoesNotExist:
            return Response({"detail": "Token not found"}, status=status.HTTP_404_NOT_FOUND)

        qr_code = token.qrcodes.order_by("-id").first()

        return Response({
            "token_id": token.token_id,
            "status": token.status,
            "category": {
                "id": token.category.id,
                "name": token.category.name,
            },
            "queue_position": token.queue_position,
            "qr_image": request.build_absolute_uri(qr_code.image.url) if qr_code and qr_code.image else None,
        })
    @action(detail=False, methods=["post"])
    def bulk_generate(self, request):
        data_list = request.data.get("data", [])
        if not isinstance(data_list, list):
            return Response({"detail": "Data must be a list."}, status=400)
        created = []
        for data in data_list:
            serializer = QRCodeSerializer(data=data)
            if serializer.is_valid():
                qr = serializer.save()
                created.append(QRCodeSerializer(qr).data)
        return Response({"created": created, "count": len(created)}, status=201)

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        try:
            qr = self.get_object()
            return Response({"detail": "QR code verified"}, status=200)
        except QRCode.DoesNotExist:
            return Response({"detail": "QR code not found"}, status=404)

    @action(detail=False, methods=["get", "post"])
    def templates(self, request):
        if request.method == "GET":
            templates = QRTemplate.objects.all()
            return Response(QRTemplateSerializer(templates, many=True).data)
        elif request.method == "POST":
            serializer = QRTemplateSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=201)
            return Response(serializer.errors, status=400)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        qr = self.get_object()
        if not qr.image or not hasattr(qr.image, "open"):
            return Response({"detail": "QR code image not found."}, status=404)
        return FileResponse(qr.image.open(), as_attachment=True, filename=f"qr_{qr.id}.png")

    @action(detail=True, methods=["get"])
    def share(self, request, pk=None):
        qr = self.get_object()
        domain = getattr(settings, "SITE_URL", "http://localhost:8000")
        share_url = f"{domain}/qr/{qr.id}/"
        return Response({"share_url": share_url})


class QRScanViewSet(viewsets.ModelViewSet):
    queryset = QRScan.objects.all().order_by("-scan_time")
    serializer_class = QRScanSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        qr_id = request.data.get("qr")
        token_id = request.data.get("token_id")
        device_type = request.data.get("device_type", "Unknown")
        if token_id and not qr_id:
            try:
                token = Token.objects.get(id=token_id)
            except Token.DoesNotExist:
                return Response({"error": "Invalid token ID"}, status=400)
            scan = QRScan.objects.create(
                qr=None,
                scanned_by=request.user,
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                device_type=device_type,
                verification_status="MANUAL",
                token=token,
            )
            # Mark token and QR as completed
            token.status = "completed"
            token.save()
            QRCode.objects.filter(token=token).update(status="completed")
            return Response({
                "scan": self.get_serializer(scan).data,
                "token_status": token.status
            }, status=201)
        try:
            qr = QRCode.objects.get(id=qr_id)
        except QRCode.DoesNotExist:
            return Response({"error": "Invalid QR code"}, status=404)
        token = qr.token
        verification_status = "SUCCESS"
        if qr.expires_at and qr.expires_at < timezone.now():
            verification_status = "FAILED"
        scan = QRScan.objects.create(
            qr=qr,
            scanned_by=request.user,
            ip_address=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            device_type=device_type,
            verification_status=verification_status,
            token=token,
        )
        return Response({
            "scan": self.get_serializer(scan).data,
            "token_status": token.status,
            "verification_status": verification_status
        }, status=status.HTTP_201_CREATED)

   


class QRSettingsViewSet(viewsets.ModelViewSet):
    queryset = QRSettings.objects.all()
    serializer_class = QRSettingsSerializer
    permission_classes = [AllowAny]


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.all().order_by("-timestamp")
    serializer_class = AuditLogSerializer
    permission_classes = [AllowAny]




from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.utils import timezone
from .models import Token, QRScan



@api_view(['GET'])
@permission_classes([AllowAny])
def category_summary(request):
    data = (
        Token.objects.values("category__name", "status")
        .annotate(count=Count("id"))
        .order_by("category__name")
    )
    return Response(list(data))

@api_view(["GET"])
@permission_classes([AllowAny])
def my_user_summary(request):
    user = request.user
    categories = user.categories.values_list("name", flat=True)
    result = {
        "username": user.username,
        "full_name": user.get_full_name() or user.username,
        "email": user.email,
        "categories": list(categories),
    }
    return Response(result)

@api_view(["GET"])
@permission_classes([AllowAny])
def session_info(request):
    return Response({
        "username": request.user.username,
        "is_authenticated": request.user.is_authenticated,
        "last_login": request.user.last_login,
        "session_expiry": request.session.get_expiry_date() if request.session else None,
    })


@api_view(["GET"])
@permission_classes([AllowAny])
def staff_tasks_overview(request):
    user = request.user
    if hasattr(user, "role") and user.role == "admin":
        tokens = Token.objects.all().order_by("-issued_at")[:10]
        scans = QRScan.objects.all().order_by("-scan_time")[:10]
    else:
        tokens = Token.objects.filter(category__in=user.categories.all()).order_by("-issued_at")[:10]
        scans = QRScan.objects.filter(scanned_by=user).order_by("-scan_time")[:10]
    token_data = TokenSerializer(tokens, many=True).data
    scan_data = ScanActivityReportSerializer(scans, many=True).data
    tasks = []
    for token in token_data:
        tasks.append({
            "type": "Token",
            "task_id": token["id"],
            "status": token["status"],
            "category": token.get("category", None),
            "issued_at": token["issued_at"],
        })
    for scan in scan_data:
        tasks.append({
            "type": "Scan",
            "task_id": scan["id"],
            "verification_status": scan["verification_status"],
            "device_type": scan["device_type"],
            "scan_time": scan["scan_time"],
        })
    tasks_sorted = sorted(tasks, key=lambda x: (
        x.get("issued_at") or x.get("scan_time")
    ), reverse=True)
    return Response({
        "username": user.username,
        "full_name": user.get_full_name() or user.username,
        "task_count": len(tasks_sorted),
        "tasks": tasks_sorted
    })



@api_view(['GET', 'POST', 'PATCH'])
@permission_classes([AllowAny])
def category_management(request):
    user = request.user
    # Admins see all categories, others see only their assigned categories
    if request.method == "GET":
        if hasattr(user, "role") and user.role == "admin":
            categories = Category.objects.all()
        elif hasattr(user, "categories"):
            categories = user.categories.all()
        else:
            categories = Category.objects.none()
        return Response([{"id": c.id, "name": c.name, "color": c.color} for c in categories])

    elif request.method == "POST":
        # Only allow admins to add new categories
        if not (hasattr(user, "role") and user.role == "admin"):
            return Response({"error": "Only admins can add categories."}, status=403)
        name = request.data.get("name")
        color = request.data.get("color", "#2563EB")
        if not name:
            return Response({"error": "Name required"}, status=400)
        category = Category.objects.create(name=name, color=color)
        return Response({"id": category.id, "name": category.name, "color": category.color})

    elif request.method == "PATCH":
        # Only allow admins to edit categories
        if not (hasattr(user, "role") and user.role == "admin"):
            return Response({"error": "Only admins can edit categories."}, status=403)
        cat_id = request.data.get("id")
        color = request.data.get("color")
        name = request.data.get("name")
        try:
            category = Category.objects.get(id=cat_id)
        except Category.DoesNotExist:
            return Response({"error": "Category not found"}, status=404)
        if color:
            category.color = color
        if name:
            category.name = name
        category.save()
        return Response({"id": category.id, "name": category.name, "color": category.color})

@api_view(["GET"])
@permission_classes([AllowAny])
def scan_count(request):
    user = request.user
    if hasattr(user, "role") and user.role == "admin":
        total = QRScan.objects.count()
        # Per-staff breakdown
        staff_counts = (
            QRScan.objects.values("scanned_by__username", "scanned_by__first_name", "scanned_by__last_name")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        return Response({
            "total_scans": total,
            "staff_counts": [
                {
                    "username": s["scanned_by__username"],
                    "full_name": f"{s['scanned_by__first_name']} {s['scanned_by__last_name']}".strip(),
                    "count": s["count"]
                }
                for s in staff_counts if s["scanned_by__username"]
            ]
        })
    else:
        count = QRScan.objects.filter(scanned_by=user).count()
        return Response({"my_scan_count": count})

@api_view(["POST"])
@permission_classes([AllowAny])
def queue_emergency(request):
    
    action = request.data.get("action")
    category_id = request.data.get("category_id")
    if action not in ["pause", "resume", "clear"]:
        return Response({"error": "Invalid action"}, status=400)

    tokens_qs = Token.objects.all()
    if category_id:
        tokens_qs = tokens_qs.filter(category_id=category_id)

    if action == "pause":
        tokens_qs.filter(status__in=["waiting", "called"]).update(status="waiting")
        return Response({"status": "paused", "affected": tokens_qs.count()})
    elif action == "resume":
        # Set first waiting token per category to "called", rest remain "waiting"
        categories = tokens_qs.values_list("category_id", flat=True).distinct()
        affected = 0
        for cat_id in categories:
            waiting = tokens_qs.filter(category_id=cat_id, status="waiting").order_by("queue_position")
            first = waiting.first()
            if first:
                first.status = "called"
                first.save()
                affected += 1
        return Response({"status": "resumed", "affected": affected})
    elif action == "clear":
        count = tokens_qs.count()
        tokens_qs.delete()
        return Response({"status": "cleared", "affected": count})


