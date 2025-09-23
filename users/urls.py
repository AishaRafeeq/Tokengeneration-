from django.urls import path, include
from .views import (
    UserViewSet,
    CurrentUserView,
    CategoryViewSet,
    staff_activity,
    staff_scan_count,
    staff_verification_logs,
    admin_dashboard_stats,
    staff_full_stats,
    staff_dashboard_stats,
    scanner_status,
    daily_report,
    staff_operational_report,
    weekly_scan_chart
)    
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'categories', CategoryViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('me/', CurrentUserView.as_view(), name='current-user'),
    path('staff-activity/', staff_activity, name='staff-activity'),
    path('staff-scan-count/', staff_scan_count, name='staff-scan-count'),
    path('staff-verification-logs/', staff_verification_logs, name='staff-verification-logs'),
    path('admin-dashboard-stats/', admin_dashboard_stats, name='admin-dashboard-stats'),
    path('staff/<int:staff_id>/full-stats/', staff_full_stats, name='staff-full-stats'),
    path('staff-dashboard-stats/', staff_dashboard_stats, name='staff-dashboard-stats'),
    path("scanner-status/", scanner_status, name="scanner-status"),
   path('daily-report/', daily_report, name='daily_report'),
   path('staff-operational-report/', staff_operational_report, name='staff-operational-report'),
   path('weekly-scan-chart/', weekly_scan_chart, name='weekly-scan-chart'),

]
