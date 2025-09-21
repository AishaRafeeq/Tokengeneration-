from django.contrib import admin
from django.urls import path, include, re_path
from django.shortcuts import redirect
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from tokens.views import TokenViewSet

router = DefaultRouter()
router.register(r'tokens', TokenViewSet, basename='token')

# Change the admin site header and title
admin.site.site_header = "Token Generation Application"
admin.site.site_title = "Token Generation Application"
admin.site.index_title = "Welcome to the Token Generation Admin"

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/', include('users.urls')),
    path('api/tokens/', include('tokens.urls')),
    path('api/scans/', include('scans.urls')),
    path('api/reports/', include('reports.urls')),
    path('api/settings/', include('settings.urls')),
    path('api/sidebar/', include('sidebar.urls')),
    path('api/', include(router.urls)),
    re_path(r'^app/admin/?$', lambda request: redirect('/admin/', permanent=True)),
]

# Serve media files only in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
