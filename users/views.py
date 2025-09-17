from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser, IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action, api_view, permission_classes
from .models import User, Category
from .serializers import UserSerializer, CategorySerializer
from tokens.models import Token, QRCode, QRScan  # adjust import if needed
from django.db.models import Count
from django.core.management.base import BaseCommand

# --- Users (Admin only for CRUD) ---
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        role = self.request.query_params.get('role')
        if role == 'staff':
            return User.objects.filter(role='staff')
        return super().get_queryset()


# --- Get current logged-in user ---
class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


# --- Categories (Public list, Admin manage) ---
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    def get_permissions(self):
        # Allow anyone to list categories (for dropdowns / TV display)
        if self.action in ["list", "retrieve", "category_settings"]:
            return [AllowAny()]
        # Only admin can create/update/delete
        return [IsAdminUser()]

    @action(detail=False, methods=["get", "post", "patch"], url_path="settings")
    def category_settings(self, request):
        if request.method == "GET":
            categories = Category.objects.all()
            serializer = CategorySerializer(categories, many=True)
            return Response(serializer.data)
        elif request.method == "POST":
            # Only admin can add
            name = request.data.get("name")
            color = request.data.get("color", "#2563EB")
            if not name:
                return Response({"error": "Name required"}, status=400)
            category = Category.objects.create(name=name, color=color)
            serializer = CategorySerializer(category)
            return Response(serializer.data)
        elif request.method == "PATCH":
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
            serializer = CategorySerializer(category)
            return Response(serializer.data)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def staff_activity(request):
    user = request.user
    username = request.GET.get("username")
    # Admin can view any staff, staff can only view their own
    if hasattr(user, "role") and user.role == "admin" and username:
        scans = QRScan.objects.filter(scanned_by__username=username).select_related("scanned_by", "qr__token__category").order_by("-scan_time")
    elif hasattr(user, "role") and user.role == "admin":
        scans = QRScan.objects.select_related("scanned_by", "qr__token__category").order_by("-scan_time")
    else:
        scans = QRScan.objects.filter(scanned_by=user).select_related("qr__token__category").order_by("-scan_time")
    activity = []
    for scan in scans:
        activity.append({
            "scan_id": scan.id,
            "staff_username": scan.scanned_by.username if scan.scanned_by else None,
            "staff_name": scan.scanned_by.get_full_name() if scan.scanned_by else None,
            "category": scan.qr.token.category.name if scan.qr and scan.qr.token and scan.qr.token.category else None,
            "token_id": scan.qr.token.token_id if scan.qr and scan.qr.token else None,
            "verification_status": scan.verification_status,
            "scan_time": scan.scan_time,
        })
    return Response(activity)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def staff_scan_count(request):
    user = request.user
    if hasattr(user, "role") and user.role == "admin":
        total = QRScan.objects.count()
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

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def staff_verification_logs(request):
    user = request.user
    if hasattr(user, "role") and user.role == "admin":
        scans = QRScan.objects.all().order_by("-scan_time")
    else:
        scans = QRScan.objects.filter(scanned_by=user).order_by("-scan_time")
    total = scans.count()
    failed = scans.filter(verification_status="FAILED").count()
    logs = []
    for scan in scans:
        logs.append({
            "scan_id": scan.id,
            "staff_username": scan.scanned_by.username if scan.scanned_by else None,
            "category": scan.token.category.name if scan.token and scan.token.category else None,
            "token_id": scan.token.token_id if scan.token else None,
            "verification_status": scan.verification_status,
            "scan_time": scan.scan_time,
        })
    return Response({
        "total_verifications": total,
        "failed_verifications": failed,
        "logs": logs
    })

@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_dashboard_stats(request):
    total_tokens = Token.objects.count()
    total_qr_codes = QRCode.objects.count()
    total_scans = QRScan.objects.count()
    total_waiting = Token.objects.filter(status="waiting").count()
    total_called = Token.objects.filter(status="called").count()
    total_completed = Token.objects.filter(status="completed").count()
    total_verifies = QRScan.objects.filter(verification_status="SUCCESS").count()
    total_failed_verifies = QRScan.objects.filter(verification_status="FAILED").count()

    return Response({
        "total_tokens": total_tokens,
        "total_qr_codes": total_qr_codes,
        "total_scans": total_scans,
        "total_waiting": total_waiting,
        "total_called": total_called,
        "total_completed": total_completed,
        "total_verifies": total_verifies,
        "total_failed_verifies": total_failed_verifies,
    })

class Command(BaseCommand):
    help = "Reset all tokens to initial state"

    def handle(self, *args, **kwargs):
        Token.objects.all().delete() 
        self.stdout.write(self.style.SUCCESS("All tokens have been reset."))
