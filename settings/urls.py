from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import QRSettingViewSet

router = DefaultRouter()
router.register('qr-settings', QRSettingViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
