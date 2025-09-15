from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from django.conf import settings
from django.conf.urls.static import static

from rest_framework.routers import DefaultRouter

router = DefaultRouter()


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/', include('users.urls')), 
    # path('api/categories/', include('categories.urls')),
    path('api/tokens/', include('tokens.urls')),
    path('api/scans/', include('scans.urls')),
    path('api/reports/', include('reports.urls')),
    path('api/settings/', include('settings.urls')),
    path('api/sidebar/', include('sidebar.urls')),
    path('api/', include(router.urls)),


] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
