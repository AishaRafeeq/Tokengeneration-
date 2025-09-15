from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.parsers import MultiPartParser
from django.utils import timezone
from django.http import FileResponse
from django.conf import settings
from django.db.models import Count
from datetime import date
from django.utils.crypto import get_random_string

from rest_framework.permissions import AllowAny
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
from rest_framework.authentication import SessionAuthentication


# ----------------------------
# Token ViewSet
# ----------------------------
# ----------------------------
# Token ViewSet
# ----------------------------
class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return  # Bypass CSRF check

from rest_framework.permissions import BasePermission

class IsStaffOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            getattr(request.user, "role", None) in ["admin", "staff"]
        )
class TokenViewSet(viewsets.ModelViewSet):
    queryset = Token.objects.all().order_by("queue_position")
    serializer_class = TokenSerializer
    permission_classes = [AllowAny]  # <--- This allows anyone to create/list tokens
    authentication_classes = [CsrfExemptSessionAuthentication]  # <--- Add this
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["token_id", "category__name", "status"]
    ordering_fields = ["issued_at", "queue_position"]
    
    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        # Admins see all, staff see only their categories
        if user.is_authenticated and getattr(user, "role", None) == "admin":
            return qs.filter(status__in=["waiting", "called"]).order_by("queue_position")
        elif user.is_authenticated:
            return qs.filter(
                status__in=["waiting", "called"],
                category__in=user.categories.all()
            ).order_by("queue_position")
        # Unauthenticated: show all (or restrict as needed)
        return qs.filter(status__in=["waiting", "called"]).order_by("queue_position")

    # -----------------------
    # Active tokens (waiting + called)
    # -----------------------
    @action(detail=False, methods=["get"])
    def active(self, request):
        tokens = self.get_queryset().filter(status__in=["waiting", "called"]).order_by("queue_position")
        return Response(TokenSerializer(tokens, many=True).data)

    # -----------------------
    # Call next token
    # -----------------------
    
    @action(detail=False, methods=["post"], permission_classes=[IsStaffOrAdmin])
    def call_next(self, request):
        # Remove all authentication/role checks here!
        qs = Token.objects.filter(status__in=["waiting", "called"]).order_by("queue_position")

        # Finish current called token if exists
        current_token = qs.filter(status="called").first()
        if current_token:
            current_token.status = "completed"
            current_token.save()

        # Get the next waiting token
        next_token = qs.filter(status="waiting").first()
        if not next_token:
            return Response({"detail": "No waiting tokens available"}, status=404)

        next_token.status = "called"
        next_token.save()

        return Response(TokenSerializer(next_token).data)

    # -----------------------
    # Complete token manually
    # -----------------------
    @action(detail=True, methods=["post"], permission_classes=[IsStaffOrAdmin])
    def complete(self, request, pk=None):
        token = self.get_object()
        token.status = "completed"
        token.save()

        # Automatically call next token
        next_token = self.get_queryset().filter(status="waiting").order_by("queue_position").first()
        if next_token:
            next_token.status = "called"
            next_token.save()
            next_token_data = TokenSerializer(next_token).data
        else:
            next_token_data = None

        return Response({
            "completed_token": TokenSerializer(token).data,
            "next_token": next_token_data
        })

    # -----------------------
    # Manual token entry
    # -----------------------
    @action(detail=False, methods=["post"], permission_classes=[IsStaffOrAdmin])
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

        # If token exists and waiting, mark as called
        if not created and token.status == "waiting":
            token.status = "called"
            token.save()

        return Response(TokenSerializer(token).data)

    # -----------------------
    # Admin: Generate token + QR (now public)
    # -----------------------
   
    @action(detail=False, methods=["post"], permission_classes=[AllowAny])
    def admin_generate(self, request):
        """
        Public: Create a new token and its QR code.
        Required POST field: category (id)
        Optional: status, issued_at
        """
        from django.utils.crypto import get_random_string

        category_id = request.data.get("category")
        status = request.data.get("status", "waiting")
        issued_at = request.data.get("issued_at", timezone.now())

        if not category_id:
            return Response({"detail": "category is required"}, status=400)

        # Generate a unique token_id (you can use any logic you want)
        token_id = get_random_string(8).upper()

        # Get category name for QR data
        try:
            category_obj = Category.objects.get(id=category_id)
            category_name = category_obj.name
        except Category.DoesNotExist:
            return Response({"detail": "Invalid category"}, status=400)

        # Auto-generate QR data (customize as needed)
        qr_data = f"{category_name}-{token_id}"

        # Create Token
        token = Token.objects.create(
            category_id=category_id,
           
            status=status,
            issued_at=issued_at,
        )

        # Create QRCode for this token
        qr_serializer = QRCodeSerializer(data={
            "token": token.id,
            "data": qr_data,
            "category": category_id,
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

    @action(detail=False, methods=["post"], permission_classes=[AllowAny])
    def public_create(self, request):
        """
        Public endpoint: Create a new token and QR code with auto-generated values.
        Required POST field: category (id)
        """
        category_id = request.data.get("category")
        status = "waiting"
        issued_at = timezone.now()

        if not category_id:
            return Response({"detail": "category is required"}, status=400)

        # Generate a unique token_id
        token_id = get_random_string(8).upper()

        # Get category name for QR data
        try:
            category_obj = Category.objects.get(id=category_id)
            category_name = category_obj.name
        except Category.DoesNotExist:
            return Response({"detail": "Invalid category"}, status=400)

        # Auto-generate QR data (customize as needed)
        qr_data = f"{category_name}-{token_id}"

        # Create Token
        token = Token.objects.create(
            category_id=category_id,
            token_id=token_id,
            status=status,
            issued_at=issued_at,
        )

        # Create QRCode for this token
        qr_serializer = QRCodeSerializer(data={
            "token": token.id,
            "data": qr_data,
            "category": category_id,
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


# ----------------------------
# QRCode ViewSet (with custom actions)
# ----------------------------
class QRCodeViewSet(viewsets.ModelViewSet):
    """
    ViewSet for QR codes, with generation, bulk, verification, templates, download, and share.
    """
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
    """
    Logs each scan and optionally validates QR expiry.
    """
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
    """
    Manage system-wide QR settings.
    """
    queryset = QRSettings.objects.all()
    serializer_class = QRSettingsSerializer
    permission_classes = [IsAdminUser]


# ----------------------------
# Reports
# ----------------------------
@api_view(["GET"])
def dashboard_overview(request):
    return Response({
        "active_tokens": Token.objects.filter(status="waiting").count(),
        "called_tokens": Token.objects.filter(status="called").count(),
        "completed_tokens": Token.objects.filter(status="completed").count(),
        "scans_today": QRScan.objects.filter(scan_time__date=date.today()).count(),
    })


@api_view(["GET"])
def operational_report(request):
    return Response({
        "tokens_today": Token.objects.filter(issued_at__date=date.today()).count(),
        "completed_today": Token.objects.filter(status="completed", issued_at__date=date.today()).count(),
        "scans_today": QRScan.objects.filter(scan_time__date=date.today()).count(),
    })


@api_view(['GET'])
def category_summary(request):
    data = (
        Token.objects.values("category__name", "status")
        .annotate(count=Count("id"))
        .order_by("category__name")
    )
    return Response(list(data))  # convert QuerySet to list



@api_view(["GET"])
@permission_classes([IsStaffOrAdmin])
def my_user_summary(request):
    """
    Returns logged-in user details along with assigned category names.
    """
    user = request.user

    # Get category names assigned to the user
    categories = user.categories.values_list("name", flat=True)  # Assuming ManyToManyField
    result = {
        "username": user.username,
        "full_name": user.get_full_name() or user.username,
        "email": user.email,
        "categories": list(categories),  # List of category names
    }

    return Response(result)


# ----------------------------
# Security
# ----------------------------
class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.all().order_by("-timestamp")
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdminUser]


@api_view(["GET"])
@permission_classes([IsStaffOrAdmin])
def session_info(request):
    return Response({
        "username": request.user.username,
        "is_authenticated": request.user.is_authenticated,
        "last_login": request.user.last_login,
        "session_expiry": request.session.get_expiry_date() if request.session else None,
    })


@api_view(["GET"])
@permission_classes([IsStaffOrAdmin])
def scan_activity_report(request):
    """
    Scan logs:
    - Staff: only their scans
    - Admin: all scans
    """
    user = request.user
    if user.role == "admin":
        scans = QRScan.objects.all().order_by("-scan_time")
    else:
        scans = QRScan.objects.filter(scanned_by=user).order_by("-scan_time")

    serializer = ScanActivityReportSerializer(scans, many=True)
    return Response(serializer.data)


# ----------------------------
# Verification Logs
# ----------------------------
@api_view(["GET"])
@permission_classes([IsStaffOrAdmin])
def verification_logs(request):
    """
    Verification logs:
    - Staff: only scans done by themselves
    - Admin: all scans
    """
    user = request.user
    if user.role == "admin":
        scans = QRScan.objects.all().order_by("-scan_time")
    else:
        scans = QRScan.objects.filter(scanned_by=user).order_by("-scan_time")

    serializer = VerificationLogSerializer(scans, many=True)
    return Response(serializer.data)


# ----------------------------
# Staff Tasks Overview
# ----------------------------
@api_view(["GET"])
@permission_classes([IsStaffOrAdmin])
def staff_tasks_overview(request):
    """
    Returns a list of tasks (tokens & scans) associated with the logged-in staff.
    - Admins: see all tasks
    - Staff: see only their own tasks
    """
    user = request.user

    # -----------------------
    # If Admin: show everything
    # -----------------------
    if user.role == "admin":
        tokens = Token.objects.all().order_by("-issued_at")[:10]  # latest 10 tokens
        scans = QRScan.objects.all().order_by("-scan_time")[:10]  # latest 10 scans
    else:
        # Staff: only tokens in assigned categories & scans they did
        tokens = Token.objects.filter(category__in=user.categories.all()).order_by("-issued_at")[:10]
        scans = QRScan.objects.filter(scanned_by=user).order_by("-scan_time")[:10]

    token_data = TokenSerializer(tokens, many=True).data
    scan_data = ScanActivityReportSerializer(scans, many=True).data

    # Build task-style output
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

    # Sort tasks by latest time
    tasks_sorted = sorted(tasks, key=lambda x: (
        x.get("issued_at") or x.get("scan_time")
    ), reverse=True)

    return Response({
        "username": user.username,
        "full_name": user.get_full_name() or user.username,
        "task_count": len(tasks_sorted),
        "tasks": tasks_sorted
    })


# ----------------------------
# Mobile Tools
# ----------------------------
@api_view(["GET"])
def quick_actions(request):
    return Response([
        {"label": "Scan Token", "action": "/api/scans/"},
        {"label": "Active Queue", "action": "/api/tokens/"},
        {"label": "Completed", "action": "/api/tokens/completed/"},
    ])


