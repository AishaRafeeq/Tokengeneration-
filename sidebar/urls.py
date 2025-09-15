from django.urls import path
from .views import SidebarView

urlpatterns = [
    path('', SidebarView.as_view(), name='sidebar'),
]
