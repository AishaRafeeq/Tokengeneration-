from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser, IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action, api_view, permission_classes
from .models import User, Category
from .serializers import UserSerializer, CategorySerializer
from tokens.models import Token, QRCode, QRScan  # adjust import if needed
from django.db.models import Count
from django.db.models import Sum
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.http import HttpResponse
import csv
from datetime import datetime
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from io import BytesIO
from collections import defaultdict
from django.db.models import Count
from django.db.models.functions import TruncDate



from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

import csv
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet






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
    success = scans.filter(verification_status="SUCCESS").count()
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
        "success_verifications": success,
        "failed_verifications": failed,
        "logs": logs
    })




@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_dashboard_stats(request):
    today = timezone.localdate()  # current date

    # Tokens created today
    total_tokens = Token.objects.filter(issued_at__date=today
).count()
    total_qr_codes = QRCode.objects.filter(generated_at__date=today
).count()

    # Scans today
    total_scans = QRScan.objects.filter(scan_time__date=today).count()
    total_success = QRScan.objects.filter(scan_time__date=today, verification_status="SUCCESS").count()
    total_failed = QRScan.objects.filter(scan_time__date=today, verification_status="FAILED").count()

    success_rate = (total_success / total_scans * 100) if total_scans > 0 else 0

    # Token statuses today
    total_waiting = Token.objects.filter(status="waiting", issued_at__date=today
).count()
    total_called = Token.objects.filter(status="called", issued_at__date=today
).count()
    total_completed = Token.objects.filter(status="completed", issued_at__date=today
).count()

    return Response({
        "total_tokens": total_tokens,
        "total_qr_codes": total_qr_codes,
        "total_scans": total_scans,
        "total_success": total_success,
        "total_failed": total_failed,
        "success_rate": round(success_rate, 2),
        "total_waiting": total_waiting,
        "total_called": total_called,
        "total_completed": total_completed,
    })



@api_view(["GET"])
@permission_classes([IsAdminUser])
def staff_full_stats(request, staff_id):
    """
    Admin: Get all stats for a specific staff user.
    """
    try:
        staff = User.objects.get(id=staff_id, role="staff")
    except User.DoesNotExist:
        return Response({"error": "Staff not found"}, status=404)

    # Categories assigned to staff
    categories = staff.categories.all()

    # Active queue tokens (waiting or called)
    active_tokens = Token.objects.filter(
        category__in=categories,
        status__in=["waiting", "called"]
    ).count()

    # Completed tokens
    completed_tokens = Token.objects.filter(
        category__in=categories,
        status="completed"
    ).count()

   
    total_scans = QRScan.objects.filter(scanned_by=staff).count()
    successful_scans = QRScan.objects.filter(scanned_by=staff, verification_status="SUCCESS").count()
    failed_scans = QRScan.objects.filter(scanned_by=staff, verification_status="FAILED").count()

    # Success rate
    success_rate = (successful_scans / total_scans * 100) if total_scans > 0 else 0

    return Response({
        "staff_id": staff.id,
        "staff_name": staff.get_full_name(),
        "categories": [c.name for c in categories],
        "active_tokens": active_tokens,
        "completed_tokens": completed_tokens,
        "total_scans": total_scans,
        "successful_scans": successful_scans,
        "failed_scans": failed_scans,
        "success_rate": round(success_rate, 2),  # percentage
    })

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def staff_dashboard_stats(request):
    user = request.user
    today = timezone.localdate()

    # Staff's categories
    categories = user.categories.all()

    # Tokens today
    total_tokens = Token.objects.filter(category__in=categories, issued_at__date=today
).count()
    total_qr_codes = QRCode.objects.filter(category__in=categories,generated_at__date=today
).count()

    # Active tokens today
    waiting_tokens = Token.objects.filter(category__in=categories, status="waiting", issued_at__date=today
).count()
    completed_tokens = Token.objects.filter(category__in=categories, status="completed", issued_at__date=today
).count()

    # Scans today
    total_scans = QRScan.objects.filter(qr__token__category__in=categories, scan_time__date=today).count()
    total_success = QRScan.objects.filter(qr__token__category__in=categories, verification_status="SUCCESS", scan_time__date=today).count()
    total_failed = QRScan.objects.filter(qr__token__category__in=categories, verification_status="FAILED", scan_time__date=today).count()

    success_rate = (total_success / total_scans * 100) if total_scans > 0 else 0

    return Response({
        "total_tokens": total_tokens,
        "total_qr_codes": total_qr_codes,
        "waiting_tokens": waiting_tokens,
        "completed_tokens": completed_tokens,
        "total_scans": total_scans,
        "total_success": total_success,
        "total_failed": total_failed,
        "success_rate": round(success_rate, 2),
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def scanner_status(request):
    """
    Returns latest scanner data for all QR scans, with optional filters:
    - status: 'SUCCESS' or 'FAILED'
    - from: start date (YYYY-MM-DD)
    - to: end date (YYYY-MM-DD)
    """
    status_filter = request.GET.get("status") 
    from_date = request.GET.get("from")       
    to_date = request.GET.get("to")            

    scans = QRScan.objects.select_related('qr', 'qr__category', 'scanned_by')

    if status_filter in ["SUCCESS", "FAILED"]:
        scans = scans.filter(verification_status=status_filter)

    if from_date:
        scans = scans.filter(scan_time__date__gte=from_date)
    if to_date:
        scans = scans.filter(scan_time__date__lte=to_date)

    scans = scans.order_by('-scan_time')[:100]

    data = []
    for scan in scans:
        data.append({
            "token_id": scan.qr.token.token_id if scan.qr and scan.qr.token else None,
            "status": scan.qr.token.status if scan.qr and scan.qr.token else None,
            "category": {
                "name": scan.qr.category.name
            } if scan.qr and scan.qr.category else None,
            "scanned_by": {
                "username": scan.scanned_by.username
            } if scan.scanned_by else None,
            "scan_time": scan.scan_time.isoformat() if scan.scan_time else None,
            "verification_status": scan.verification_status,
        })
    return Response(data)









def generate_pdf(report_data, start_date, end_date, include_staff=True):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []

    styles = getSampleStyleSheet()

    # Title
    title = Paragraph(f"<b>Daily Report ({start_date} to {end_date})</b>", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 12))

    # Summary
    summary_data = [
        ["Total QR Codes", report_data["total_qr_codes"]],
        ["Completed QR Codes", report_data["completed_qr_codes"]],
        ["Success Verifications", report_data["success_verifications"]],
        ["Failed Verifications", report_data["failed_verifications"]],
    ]
    summary_table = Table(summary_data, colWidths=[200, 200])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
    ]))
    elements.append(Paragraph("<b>Summary</b>", styles['Heading2']))
    elements.append(summary_table)
    elements.append(Spacer(1, 20))

    # Category Summary
    category_data = [["Category", "Total QR", "Staff Assigned"]]
    for c in report_data["categories"]:
        staff_str = ", ".join(c["staff_assigned"]) if c["staff_assigned"] else "No staff assigned"
        category_data.append([c["category"], c["total_qr"], staff_str])

    category_table = Table(category_data, colWidths=[150, 100, 250])
    category_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
    ]))
    elements.append(Paragraph("<b>Category Summary</b>", styles['Heading2']))
    elements.append(category_table)
    elements.append(Spacer(1, 20))

    # Staff Summary (Admin only)
    if include_staff:
        staff_data = [["Staff", "Waiting Tokens", "Completed", "Success", "Failed"]]
        for s in report_data["staff_summary"]:
            staff_data.append([
                s["staff"],
                s["waiting_tokens"],
                s["completed_tokens"],
                s["success_verifications"],
                s["failed_verifications"]
            ])

        staff_table = Table(staff_data, colWidths=[120, 100, 100, 100, 100])
        staff_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ]))
        elements.append(Paragraph("<b>Staff Summary</b>", styles['Heading2']))
        elements.append(staff_table)

    doc.build(elements)
    buffer.seek(0)
    return buffer


# ---------------- CSV Export ---------------- #
def export_csv(report_data, start_date, end_date, include_staff=True):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="daily_report_{start_date}_to_{end_date}.csv"'

    writer = csv.writer(response)

    # Summary
    writer.writerow(["Daily Report", f"{start_date} to {end_date}"])
    writer.writerow([])
    writer.writerow(["Summary"])
    writer.writerow(["Total QR Codes", report_data["total_qr_codes"]])
    writer.writerow(["Completed QR Codes", report_data["completed_qr_codes"]])
    writer.writerow(["Success Verifications", report_data["success_verifications"]])
    writer.writerow(["Failed Verifications", report_data["failed_verifications"]])
    writer.writerow([])

    # Category Summary
    writer.writerow(["Category Summary"])
    writer.writerow(["Category", "Total QR", "Staff Assigned"])
    for c in report_data["categories"]:
        staff_str = ", ".join(c["staff_assigned"]) if c["staff_assigned"] else "No staff assigned"
        writer.writerow([c["category"], c["total_qr"], staff_str])
    writer.writerow([])

    # Staff Summary (Admin only)
    if include_staff:
        writer.writerow(["Staff Summary"])
        writer.writerow(["Staff", "Waiting Tokens", "Completed", "Success", "Failed"])
        for s in report_data["staff_summary"]:
            writer.writerow([
                s["staff"],
                s["waiting_tokens"],
                s["completed_tokens"],
                s["success_verifications"],
                s["failed_verifications"]
            ])

    return response


# ---------------- API View ---------------- #
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def daily_report(request):
    start_date = request.GET.get('start_date') or timezone.localtime().date()
    end_date = request.GET.get('end_date') or timezone.localtime().date()

    scans = QRScan.objects.filter(
        scan_time__date__range=[start_date, end_date]
    ).select_related("scanned_by", "qr__token__category")

    user = request.user
    username = request.GET.get("username")
    if hasattr(user, "role") and user.role != "admin":
        scans = scans.filter(scanned_by=user)
    elif hasattr(user, "role") and user.role == "admin" and username:
        scans = scans.filter(scanned_by__username=username)

    # Staff activity
    staff_map = defaultdict(lambda: {"waiting": 0, "completed": 0, "success": 0, "failed": 0})
    for scan in scans:
        if scan.qr and scan.qr.token:
            token_status = scan.qr.token.status
            staff_map[scan.scanned_by.username]["waiting" if token_status == "waiting" else "completed"] += 1
        if scan.verification_status == "SUCCESS":
            staff_map[scan.scanned_by.username]["success"] += 1
        elif scan.verification_status == "FAILED":
            staff_map[scan.scanned_by.username]["failed"] += 1

    staff_summary = []
    for staff, counts in staff_map.items():
        staff_summary.append({
            "staff": staff,
            "waiting_tokens": counts["waiting"],
            "completed_tokens": counts["completed"],
            "success_verifications": counts["success"],
            "failed_verifications": counts["failed"]
        })

    # Categories
    categories = []
    for category in Category.objects.all():
        total_qr = QRCode.objects.filter(token__category=category).count()
        staff_assigned = [s.username for s in category.staff_members.all()]
        categories.append({
            "category": category.name,
            "total_qr": total_qr,
            "staff_assigned": staff_assigned
        })

    # Totals
    total_qr_codes = QRCode.objects.filter(token__issued_at__date__range=[start_date, end_date]).count()
    completed_qr_codes = QRCode.objects.filter(
        token__status='completed',
        token__issued_at__date__range=[start_date, end_date]
    ).count()
    success_verifications = scans.filter(verification_status='SUCCESS').count()
    failed_verifications = scans.filter(verification_status='FAILED').count()

    data = {
        "total_qr_codes": total_qr_codes,
        "completed_qr_codes": completed_qr_codes,
        "success_verifications": success_verifications,
        "failed_verifications": failed_verifications,
        "staff_summary": staff_summary,
        "categories": categories
    }

    export_type = request.GET.get("export")
    include_staff = hasattr(user, "role") and user.role == "admin"

    if export_type == "pdf":
        pdf_buffer = generate_pdf(data, start_date, end_date, include_staff)
        response = HttpResponse(pdf_buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="daily_report_{start_date}_to_{end_date}.pdf"'
        return response

    if export_type == "csv":
        return export_csv(data, start_date, end_date, include_staff)

    return Response(data)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def staff_operational_report(request):
    """
    Staff: View their own operational report (tokens + scans).
    Admin: Can view all staff reports or filter by ?username=<staff_username>.
    """
    user = request.user
    today = timezone.localdate()
    username = request.GET.get("username")

    # If admin, allow filtering by username
    if getattr(user, "role", None) == "admin" and username:
        from users.models import User
        try:
            staff_user = User.objects.get(username=username, role="staff")
        except User.DoesNotExist:
            return Response({"error": "Staff not found"}, status=404)
    else:
        staff_user = user

    
    categories = staff_user.categories.all()

    total_tokens = Token.objects.filter(category__in=categories, issued_at__date=today).count()
    waiting_tokens = Token.objects.filter(category__in=categories, status="waiting", issued_at__date=today).count()
    completed_tokens = Token.objects.filter(category__in=categories, status="completed", issued_at__date=today).count()

    
    scans_today = QRScan.objects.filter(scanned_by=staff_user, scan_time__date=today)
    total_scans = scans_today.count()
    success_scans = scans_today.filter(verification_status="SUCCESS").count()
    failed_scans = scans_today.filter(verification_status="FAILED").count()
    success_rate = round((success_scans / total_scans * 100), 2) if total_scans > 0 else 0

    
    report = {
        "Username": staff_user.username,
        "Report date": str(today),
        "categories": [c.name for c in categories],
        "tokens": {
            "total": total_tokens,
            "waiting": waiting_tokens,
            "completed": completed_tokens,
        },
        "scans": {
            "total": total_scans,
            "success": success_scans,
            "failed": failed_scans,
            
        }
    }

    return Response(report)

@api_view(["GET"])
@permission_classes([IsAdminUser])
def weekly_scan_chart(request):
    today = timezone.localdate()
    start_date = today - timedelta(days=6)  # last 7 days including today

    # Aggregate scans per day
    scans = (
        QRScan.objects.filter(scan_time__date__range=[start_date, today])
        .annotate(day=TruncDate('scan_time'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )

    # Fill missing days with 0
    chart_data = []
    for i in range(7):
        day = start_date + timedelta(days=i)
        count = next((s['count'] for s in scans if s['day'] == day), 0)
        chart_data.append({
            "date": day.strftime("%a"),  # e.g., "Mon", "Tue"
            "scans": count
        })

    return Response(chart_data)    
class Command(BaseCommand):
    help = "Reset all tokens to initial state"

    def handle(self, *args, **kwargs):
        Token.objects.all().delete() 
        self.stdout.write(self.style.SUCCESS("All tokens have been reset."))

