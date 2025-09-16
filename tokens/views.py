from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser
from django.utils import timezone
from django.http import FileResponse
from django.conf import settings
from django.db.models import Count
from datetime import date, timedelta
from django.utils.crypto import get_random_string

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

# ----------------------------
# Token ViewSet
# ----------------------------
class TokenViewSet(viewsets.ModelViewSet):
    queryset = Token.objects.all().order_by("queue_position")
    serializer_class = TokenSerializer
    permission_classes = [AllowAny]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["token_id", "category__name", "status"]
    ordering_fields = ["issued_at", "queue_position"]

    def get_queryset(self):
        return super().get_queryset().filter(status__in=["waiting", "called"]).order_by("queue_position")

    @action(detail=False, methods=["get"])
    def active(self, request):
        tokens = self.get_queryset().filter(status__in=["waiting", "called"]).order_by("queue_position")
        return Response(TokenSerializer(tokens, many=True).data)

    @action(detail=False, methods=["post"])
    def call_next(self, request):
        qs = Token.objects.filter(status__in=["waiting", "called"]).order_by("queue_position")
        current_token = qs.filter(status="called").first()
        if current_token:
            current_token.status = "completed"
            current_token.save()
        next_token = qs.filter(status="waiting").first()
        if not next_token:
            return Response({"detail": "No waiting tokens available"}, status=404)
        next_token.status = "called"
        next_token.save()
        return Response(TokenSerializer(next_token).data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        token = self.get_object()
        token.status = "completed"
        token.save()
        next_token = self.get_queryset().filter(status="waiting").order_by("queue_position").first()
        next_token_data = TokenSerializer(next_token).data if next_token else None
        return Response({
            "completed_token": TokenSerializer(token).data,
            "next_token": next_token_data
        })

    @action(detail=False, methods=["post"])
    def manual_call(self, request):
        token_id = request.data.get("token_id")
        category_id = request.data.get("category_id")
        if not token_id:
            return Response({"detail": "token_id is required"}, status=400)
        token, created = Token.objects.get_or_create(
            id=token_id,
            defaults={
                "category_id": category_id,
                "status": "called",
                "issued_at": timezone.now(),
            }
        )
        if not created and token.status == "waiting":
            token.status = "called"
            token.save()
        return Response(TokenSerializer(token).data)

    @action(detail=False, methods=["post"])
    def admin_generate(self, request):
        category_id = request.data.get("category")
        status = request.data.get("status", "waiting")
        issued_at = request.data.get("issued_at", timezone.now())
        if not category_id:
            return Response({"detail": "category is required"}, status=400)
        token_id = get_random_string(8).upper()
        try:
            category_obj = Category.objects.get(id=category_id)
            category_name = category_obj.name
        except Category.DoesNotExist:
            return Response({"detail": "Invalid category"}, status=400)
        qr_data = f"{category_name}-{token_id}"
        token = Token.objects.create(
            category_id=category_id,
            status=status,
            issued_at=issued_at,
        )
        qr_serializer = QRCodeSerializer(data={
            "token": token.id,
            "category": category_id,
            "data": qr_data,
        })
        if qr_serializer.is_valid():
            qr = qr_serializer.save()
        else:
            token.delete()
            return Response({
                "detail": "QR code creation failed",
                "errors": qr_serializer.errors
            }, status=400)
        return Response({
            "token": TokenSerializer(token).data,
            "qr_code": QRCodeSerializer(qr).data,
        }, status=201)

    @action(detail=False, methods=['post'], url_path='public-create')
    def public_create(self, request):
        category_id = request.data.get("category")
        if not category_id:
            return Response({"error": "Category required"}, status=400)
        try:
            category = Category.objects.get(id=category_id)
        except Category.DoesNotExist:
            return Response({"error": "Invalid category"}, status=400)
        token = Token.objects.create(category=category, status="waiting")
        expires_at = timezone.now() + timedelta(hours=24)
        # Check if QRCode already exists for this token
        qr_code, created = QRCode.objects.get_or_create(
            token=token,
            defaults={
                "category": category,
                "expires_at": expires_at,
            }
        )
        qr_data = QRCodeSerializer(qr_code, context={"request": request}).data
        return Response({
            "token": {
                "token_id": token.token_id,
                "status": token.status,
                "category": {
                    "id": category.id,
                    "name": category.name,
                },
            },
            "qr_code": qr_data,
        }, status=201)

# ----------------------------
# QRCode ViewSet
# ----------------------------
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

# ----------------------------
# QRScan ViewSet
# ----------------------------
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

# ----------------------------
# QRSettings ViewSet
# ----------------------------
class QRSettingsViewSet(viewsets.ModelViewSet):
    queryset = QRSettings.objects.all()
    serializer_class = QRSettingsSerializer
    permission_classes = [AllowAny]

# ----------------------------
# AuditLog ViewSet
# ----------------------------
class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.all().order_by("-timestamp")
    serializer_class = AuditLogSerializer
    permission_classes = [AllowAny]

# ----------------------------
# Function-based views for reports and mobile tools
# ----------------------------
@api_view(["GET"])
@permission_classes([AllowAny])
def dashboard_overview(request):
    user = request.user
    if hasattr(user, "role") and user.role == "admin":
        active_tokens = Token.objects.filter(status="waiting").count()
        called_tokens = Token.objects.filter(status="called").count()
        completed_tokens = Token.objects.filter(status="completed").count()
        scans_today = QRScan.objects.filter(scan_time__date=date.today()).count()
    else:
        categories = getattr(user, "categories", None)
        if categories is not None:
            active_tokens = Token.objects.filter(
                status="waiting", category__in=categories.all()
            ).count()
            called_tokens = Token.objects.filter(
                status="called", category__in=categories.all()
            ).count()
            completed_tokens = Token.objects.filter(
                status="completed", category__in=categories.all()
            ).count()
        else:
            active_tokens = called_tokens = completed_tokens = 0
        scans_today = QRScan.objects.filter(
            scanned_by=user, scan_time__date=date.today()
        ).count()
    return Response({
        "active_tokens": active_tokens,
        "called_tokens": called_tokens,
        "completed_tokens": completed_tokens,
        "scans_today": scans_today,
    })

@api_view(["GET"])
@permission_classes([AllowAny])
def operational_report(request):
    return Response({
        "tokens_today": Token.objects.filter(issued_at__date=date.today()).count(),
        "completed_today": Token.objects.filter(status="completed", issued_at__date=date.today()).count(),
        "scans_today": QRScan.objects.filter(scan_time__date=date.today()).count(),
    })

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
def scan_activity_report(request):
    user = request.user
    if hasattr(user, "role") and user.role == "admin":
        scans = QRScan.objects.all().order_by("-scan_time")
    else:
        scans = QRScan.objects.filter(scanned_by=user).order_by("-scan_time")
    serializer = ScanActivityReportSerializer(scans, many=True)
    return Response(serializer.data)

@api_view(["GET"])
@permission_classes([AllowAny])
def verification_logs(request):
    user = request.user
    if hasattr(user, "role") and user.role == "admin":
        scans = QRScan.objects.all().order_by("-scan_time")
    else:
        scans = QRScan.objects.filter(scanned_by=user).order_by("-scan_time")
    serializer = VerificationLogSerializer(scans, many=True)
    return Response(serializer.data)

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

@api_view(["GET"])
@permission_classes([AllowAny])
def quick_actions(request):
    return Response([
        {"label": "Scan Token", "action": "/api/scans/"},
        {"label": "Active Queue", "action": "/api/tokens/"},
        {"label": "Completed", "action": "/api/tokens/completed/"},
    ])


