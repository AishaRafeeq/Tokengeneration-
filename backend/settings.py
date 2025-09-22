"""
Django settings for backend project.
"""

from pathlib import Path
import os
import dj_database_url
from datetime import timedelta
from backend.whitenoise_headers import add_headers  # ✅ import callable

BASE_DIR = Path(__file__).resolve().parent.parent


SECRET_KEY = 'django-insecure-gfcnu368d&5af0a@x(ns0&nwq+_2buu68u_q7k%91+(wrpr5j&'


DEBUG = False  

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "tokengeneration-backend.onrender.com",
    "tokengeneration-backend-1.onrender.com",
    "tokengeneration-f665.onrender.com",
    "frontend-tokengen.netlify.app",
    "public-token-generate.netlify.app",
    "https://tokengen-react.onrender.com",
]

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:3000",
    "https://public-token-generate.netlify.app",
    "https://public-display.netlify.app",
    "https://token-public-display.netlify.app", 
    "https://tokengeneration-f665.onrender.com",
    "https://frontend-tokengen.netlify.app",
    "https://tokengen-react.onrender.com",
]

CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "access-control-allow-origin",
]
CORS_ALLOW_METHODS = ["DELETE", "GET", "OPTIONS", "PATCH", "POST", "PUT"]
CORS_EXPOSE_HEADERS = ["Content-Type", "Access-Control-Allow-Origin"]
CORS_ALLOW_CREDENTIALS = True

# ---------------- Apps ---------------- #
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "import_export",
    "rest_framework",
    "qr_code",
    "users",
    "categories",
    "tokens",
    "scans",
    "reports",
    "settings",
    "sidebar",
    "corsheaders",
]

AUTH_USER_MODEL = "users.User"  # Custom User model

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",  # Must be first
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "backend.middleware.MediaCORSMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "backend.wsgi.application"

# ---------------- Database ---------------- #
DATABASES = {
    "default": dj_database_url.parse(
        "postgresql://token_generation_user:ieG46Xx3oAebVHrIpC2zF7abgRh8Y9Iy@dpg-d30o4395pdvs7388oh90-a.oregon-postgres.render.com/token_generation",
        conn_max_age=600,
        ssl_require=True,
    )
}

# ---------------- Auth ---------------- #
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------- Locale ---------------- #
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_TZ = True

# ---------------- Static & Media ---------------- #
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Use HTTPS for media URLs
MEDIA_URL = '/media/'
MEDIA_ROOT = '/app/media'

# ---------------- REST Framework ---------------- #
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
}

# ---------------- JWT ---------------- #
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# ---------------- CSRF ---------------- #
CSRF_TRUSTED_ORIGINS = [
    "https://tokengeneration-backend.onrender.com",
    "https://tokengeneration-backend-1.onrender.com",
    "https://tokengeneration-f665.onrender.com",
    "https://public-token-generate.netlify.app",
    "https://frontend-tokengen.netlify.app",
    "https://tokengen-react.onrender.com",
]

# ---------------- WhiteNoise ---------------- #
WHITENOISE_ADD_HEADERS_FUNCTION = add_headers

# ---------------- HTTPS ---------------- #

# ---------------- Docker / Production Media Fix ---------------- #
# Ensure media directory exists for QR code generation
if not os.path.exists(MEDIA_ROOT):
    os.makedirs(MEDIA_ROOT, exist_ok=True)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
