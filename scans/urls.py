from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ScanViewSet

router = DefaultRouter()
router.register('scans', ScanViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
