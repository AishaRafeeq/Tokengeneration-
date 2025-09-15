from rest_framework.views import APIView
from rest_framework.response import Response
from tokens.models import Token
from scans.models import Scan

class ReportsView(APIView):
    def get(self, request):
        total_tokens = Token.objects.count()
        scanned_tokens = Scan.objects.count()
        waiting_tokens = Token.objects.filter(status='waiting').count()
        in_progress_tokens = Token.objects.filter(status='in_progress').count()
        completed_tokens = Token.objects.filter(status='completed').count()
        return Response({
            'total_tokens': total_tokens,
            'scanned_tokens': scanned_tokens,
            'waiting_tokens': waiting_tokens,
            'in_progress_tokens': in_progress_tokens,
            'completed_tokens': completed_tokens
        })
