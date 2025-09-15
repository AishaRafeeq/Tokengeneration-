from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, CurrentUserView, CategoryViewSet

router = DefaultRouter()
router.register('users', UserViewSet)
router.register('categories', CategoryViewSet)

urlpatterns = [
    path('users/current/', CurrentUserView.as_view(), name='current-user'),  # move outside router
    path('', include(router.urls)),  # include router last
]
