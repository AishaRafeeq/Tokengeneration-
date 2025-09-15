from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import Scan
from .serializers import ScanSerializer

class ScanViewSet(viewsets.ModelViewSet):
    queryset = Scan.objects.all()
    serializer_class = ScanSerializer

    def get_permissions(self):
        # Staff can view and create scans, not delete
        return [IsAuthenticated()]
