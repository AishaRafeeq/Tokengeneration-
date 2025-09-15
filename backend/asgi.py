import os
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application
import tokens.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'qr_token_system.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(tokens.routing.websocket_urlpatterns)
    ),
})
