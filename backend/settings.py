"""
Django settings for backend project.
"""

from pathlib import Path
import os
import dj_database_url
from datetime import timedelta
from backend.whitenoise_headers import add_headers 

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-gfcnu368d&5af0a@x(ns0&nwq+_2buu68u_q7k%91+(wrpr5j&'

DEBUG = True 

ALLOWED_HOSTS = ["*"]

# ---------------- CORS ---------------- #
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
    "http://localhost:3003",
    "http://localhost:3004",

    # Deployed domains
    "https://public-token-generate.netlify.app",
    "https://tokengeneration-f665.onrender.com",
    "https://tokengeneration-public.onrender.com",
    "https://practitioners-semester-assumed-attention.trycloudflare.com",
    "https://conduct-footage-jeremy-opinion.trycloudflare.com",
    "https://geometry-sympathy-investigated-ratings.trycloudflare.com",
    "https://sign-near-whose-professor.trycloudflare.com",
    "https://model-following-alot-revision.trycloudflare.com",
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

    # Third-party
    "import_export",
    "rest_framework",
    "corsheaders",
    "qr_code",

    # Local apps
    "users",
    "categories",
    "tokens",
    "scans",
    "reports",
    "settings",
    "sidebar",
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
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
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

MEDIA_URL = "/media/"
MEDIA_ROOT = "/app/media"

# ---------------- DRF ---------------- #
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
    "https://public-token-generate.netlify.app",
    "https://tokengeneration-f665.onrender.com",
    "https://tokengeneration-public.onrender.com",
    "https://practitioners-semester-assumed-attention.trycloudflare.com",
    "https://conduct-footage-jeremy-opinion.trycloudflare.com",
    "https://geometry-sympathy-investigated-ratings.trycloudflare.com",
    "https://sign-near-whose-professor.trycloudflare.com",
    "https://model-following-alot-revision.trycloudflare.com",
]

# ---------------- WhiteNoise ---------------- #
WHITENOISE_ADD_HEADERS_FUNCTION = add_headers

if not os.path.exists(MEDIA_ROOT):
    os.makedirs(MEDIA_ROOT, exist_ok=True)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
