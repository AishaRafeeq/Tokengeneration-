# backend/middleware.py

from django.utils.deprecation import MiddlewareMixin
from django.conf import settings

class MediaCORSMiddleware(MiddlewareMixin):
    """
    Ensures CORS headers are added to /media/ file responses
    so frontend (React/Netlify/etc) can fetch QR code images.
    """
    def process_response(self, request, response):
        if request.path.startswith(settings.MEDIA_URL):
            response["Access-Control-Allow-Origin"] = "*"
            response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
            response["Access-Control-Allow-Headers"] = "Origin, Content-Type, Accept, Authorization"
        return response
