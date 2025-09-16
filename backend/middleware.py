from django.utils.deprecation import MiddlewareMixin
from django.conf import settings

class MediaCORSMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if request.path.startswith(settings.MEDIA_URL):
            response["Access-Control-Allow-Origin"] = "*"
            response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
            response["Access-Control-Allow-Headers"] = "Origin, Content-Type, Accept, Authorization"
        return response
