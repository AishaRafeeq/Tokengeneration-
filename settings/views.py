from rest_framework import viewsets
from .models import QRSetting
from .serializers import QRSettingSerializer
from rest_framework.permissions import IsAdminUser

class QRSettingViewSet(viewsets.ModelViewSet):
    queryset = QRSetting.objects.all()
    serializer_class = QRSettingSerializer
    permission_classes = [IsAdminUser]
