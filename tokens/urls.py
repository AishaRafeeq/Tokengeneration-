# src/api/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TokenViewSet,
    QRCodeViewSet,
    QRScanViewSet,
    QRSettingsViewSet,
    AuditLogViewSet,
    dashboard_overview,
    operational_report,
    category_summary,
    session_info,
    quick_actions,
    my_user_summary,
    scan_activity_report,
    verification_logs,
    operational_report,
    staff_tasks_overview
)

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r'tokens', TokenViewSet, basename='token')
router.register(r'qr', QRCodeViewSet, basename='qr')
router.register(r'scans', QRScanViewSet, basename='qrscans')
router.register(r'settings', QRSettingsViewSet, basename='qrsettings')
router.register(r'audit', AuditLogViewSet, basename='auditlogs')

# The API URLs are now determined automatically by the router
urlpatterns = [
    path('', include(router.urls)),

    # Additional non-ViewSet endpoints
    path('my-summary/', my_user_summary, name='my-user-summary'),
    path('dashboard/', dashboard_overview, name='dashboard-overview'),
    path('reports/operational/', operational_report, name='operational-report'),
    path('category-summary/', category_summary, name='category-summary'),
    path('session/', session_info, name='session-info'),
    path('quick-actions/', quick_actions, name='quick-actions'),
    path('scan-activity/', scan_activity_report, name='scan-activity-report'),
    path('verification-logs/', verification_logs, name='verification-logs'),
    path('operational/', operational_report, name='operational-report'),
    path('staff-tasks/', staff_tasks_overview, name='staff-tasks-overview'),
    path('admin-generate/', TokenViewSet.as_view({'post': 'admin_generate'}), name='admin-generate-token'),
    path('public/<str:token_id>/', TokenViewSet.as_view({'get': 'public'}), name='public-token-retrieve'),
    path('public-generate/', TokenViewSet.as_view({'post': 'public_generate'}), name='public-generate-token'),
    path('public-latest/', TokenViewSet.as_view({'get': 'public_latest'}), name='public-latest-token'),
    path('admin-tokens/', TokenViewSet.as_view({'get': 'admin_tokens'}), name='admin-tokens-list'),
]
