from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import SidebarSection
from .serializers import SidebarSectionSerializer

class SidebarView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        role = getattr(user, 'role', None)

        if not role:
            return Response({'error': 'User has no role field.'}, status=500)

        if role == 'admin':
            sections = SidebarSection.objects.filter(visible_to_admin=True).order_by('order')
        elif role == 'staff':
            sections = SidebarSection.objects.filter(visible_to_staff=True).order_by('order')
        else:
            sections = SidebarSection.objects.none()

        serializer = SidebarSectionSerializer(sections, many=True)
        return Response(serializer.data)
