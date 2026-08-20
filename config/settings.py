"""
Django settings for the Bestie Books backend (config project).

Core objectives targeted by this settings module:
- Custom user model (accounts.User) supporting Reader / Author / Admin roles
- SQLite for local development, PostgreSQL in staging/production (env-driven)
- Django REST Framework + JWT auth, ready for web + mobile clients
- CORS enabled for the Next.js frontend / Flutter app during development
"""

from pathlib import Path
from datetime import timedelta
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent

# ------------------------------------------------------------------
# Core / security
# ------------------------------------------------------------------
SECRET_KEY = config("SECRET_KEY", default="django-insecure-change-me-in-.env")
DEBUG = config("DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())

# ------------------------------------------------------------------
# Applications
# ------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",

    # Bestie Books domain apps
    "common",
    "accounts",
    "catalog",
    "orders",
    "payments",
    "reader",
    "reviews",
    "notifications",
    "coupons",
    "payouts",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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

WSGI_APPLICATION = "config.wsgi.application"

# ------------------------------------------------------------------
# Database
# Local dev defaults to SQLite. Set DB_ENGINE=postgres (+ DB_* vars) in
# .env for staging/production, matching the protocol's PostgreSQL choice.
# ------------------------------------------------------------------
if config("DB_ENGINE", default="sqlite") == "postgres":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("DB_NAME", default="bestiebooks"),
            "USER": config("DB_USER", default="bestiebooks"),
            "PASSWORD": config("DB_PASSWORD", default=""),
            "HOST": config("DB_HOST", default="localhost"),
            "PORT": config("DB_PORT", default="5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ------------------------------------------------------------------
# Auth
# ------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ------------------------------------------------------------------
# DRF / JWT
# ------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

# ------------------------------------------------------------------
# CORS (dev-friendly defaults; tighten for production)
# ------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:3000",
    cast=Csv(),
)

# ------------------------------------------------------------------
# I18N / TZ
# ------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ------------------------------------------------------------------
# Static / Media
# ------------------------------------------------------------------
STATIC_URL = "static/"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# ------------------------------------------------------------------
# MTN MoMo (Collections API) - https://momodeveloper.mtn.com
# Sandbox by default; swap MOMO_BASE_URL + MOMO_TARGET_ENVIRONMENT for
# production once MTN approves the go-live application.
# ------------------------------------------------------------------
MOMO_BASE_URL = config("MOMO_BASE_URL", default="https://sandbox.momodeveloper.mtn.com")
MOMO_TARGET_ENVIRONMENT = config("MOMO_TARGET_ENVIRONMENT", default="sandbox")
MOMO_SUBSCRIPTION_KEY = config("MOMO_SUBSCRIPTION_KEY", default="")
MOMO_API_USER = config("MOMO_API_USER", default="")
MOMO_API_KEY = config("MOMO_API_KEY", default="")
MOMO_CALLBACK_URL = config("MOMO_CALLBACK_URL", default="")  # public HTTPS URL for async callbacks

# ------------------------------------------------------------------
# Airtel Money (Openweb Collections API) - https://developers.airtel.africa
# ------------------------------------------------------------------
AIRTEL_BASE_URL = config("AIRTEL_BASE_URL", default="https://openapiuat.airtel.africa")
AIRTEL_CLIENT_ID = config("AIRTEL_CLIENT_ID", default="")
AIRTEL_CLIENT_SECRET = config("AIRTEL_CLIENT_SECRET", default="")
AIRTEL_COUNTRY = config("AIRTEL_COUNTRY", default="RW")
AIRTEL_CURRENCY = config("AIRTEL_CURRENCY", default="RWF")

# ------------------------------------------------------------------
# Flutterwave Standard (v3) - https://developer.flutterwave.com
# Covers cards, bank transfer, and mobile money via one hosted checkout.
# ------------------------------------------------------------------
FLUTTERWAVE_BASE_URL = config("FLUTTERWAVE_BASE_URL", default="https://api.flutterwave.com")
FLUTTERWAVE_SECRET_KEY = config("FLUTTERWAVE_SECRET_KEY", default="")
FLUTTERWAVE_WEBHOOK_SECRET_HASH = config("FLUTTERWAVE_WEBHOOK_SECRET_HASH", default="")
FRONTEND_URL = config("FRONTEND_URL", default="http://localhost:3000")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
