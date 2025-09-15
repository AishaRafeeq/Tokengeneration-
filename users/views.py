from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser, IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import User, Category
from .serializers import UserSerializer, CategorySerializer

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
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]
        # Only admin can create/update/delete
        return [IsAdminUser()]
