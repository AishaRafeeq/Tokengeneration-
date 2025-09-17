from django.urls import path, include
from .views import (
    UserViewSet, CurrentUserView, CategoryViewSet,
    staff_activity, staff_scan_count, staff_verification_logs,
    admin_dashboard_stats,
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
]
