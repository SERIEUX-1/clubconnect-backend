"""
CLUBCONNECT — Django settings.

Design decisions (see /docs/architecture.md for the full rationale):
- All secrets come from environment variables. Nothing sensitive is hard-coded.
- Business logic (scoring, permissions, criteria) lives in apps/*, never in
  frontend JS and never as constants buried in views.
- Every domain in the PRS's Information Architecture is its own Django app,
  so ownership and testing stay isolated and the system can grow for years
  without becoming a monolith of tangled logic.
"""
import os
from datetime import timedelta
from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
)
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))


SECRET_KEY = env("DJANGO_SECRET_KEY", default="change-me-in-.env")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "testserver"])

# --------------------------------------------------------------------------
# Applications
# --------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "django_filters",
    "corsheaders",
]

# One app per module in the PRS Information Architecture (Section 5).
LOCAL_APPS = [
    "apps.core",            # shared mixins: audit, base permissions, base models
    "apps.accounts",        # Authentication & Identity
    "apps.clubs",           # Club Directory + Digital Passport + Portfolio
    "apps.activities",      # Activities
    "apps.events",          # Events
    "apps.attendance",      # Events & Attendance (QR)
    "apps.evidence",        # Evidence Vault
    "apps.collaborations",  # Collaborations
    "apps.impact",          # Projects & Impact
    "apps.reporting",       # Monthly Reporting
    "apps.evaluation",      # Performance & Scoring + CCEA cycles
    "apps.ai_assistant",    # AI Evaluation Assistant + AI Club Coach
    "apps.notifications.apps.NotificationsConfig",
    "apps.awards",          # CCEA Awards + Hall of Excellence
    "apps.resources",       # Resource Hub
    "apps.audit",           # Audit & Governance
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.audit.middleware.CurrentUserMiddleware",  # makes request.user available to signal-based audit logging
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --------------------------------------------------------------------------
# Database — PostgreSQL in every real environment, per PRS Section 14.
# --------------------------------------------------------------------------
DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres://clubconnect:clubconnect@localhost:5432/clubconnect")
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TIME_ZONE", default="Indian/Mauritius")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
Path(STATIC_ROOT).mkdir(parents=True, exist_ok=True)

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
# Evidence files: local disk in development; S3-compatible when AWS_STORAGE_BUCKET_NAME is set.
from apps.core.storage import default_storage_backend, static_storage_backend

STORAGES = {
    "default": {"BACKEND": default_storage_backend()},
    "staticfiles": {"BACKEND": static_storage_backend()},
}
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME", default="")
AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default="")
AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL", default="") or None
AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default="")
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default="")
AWS_S3_CUSTOM_DOMAIN = env("AWS_S3_CUSTOM_DOMAIN", default="")
AWS_DEFAULT_ACL = None
AWS_QUERYSTRING_AUTH = True
BACKUP_DIR = env("BACKUP_DIR", default=str(BASE_DIR / "var" / "backups"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------
# DRF / Auth
# --------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.core.authentication.RelaxedJWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 100,
    "DEFAULT_THROTTLE_CLASSES": ("rest_framework.throttling.ScopedRateThrottle",),
    "DEFAULT_THROTTLE_RATES": {
        "attendance-scan": "10/min",
        "auth": "10/min",
        "licence-inquiry": "8/hour",
        "help-ticket": "12/hour",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=12),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:5173", "http://127.0.0.1:5174"],
)
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8000", "http://127.0.0.1:8000"],
)

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=True)
    CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=True)
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)
    SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=0)
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"

# --------------------------------------------------------------------------
# AI provider abstraction — never hard-code a specific vendor SDK call
# outside apps/ai_assistant/services.py (PRS Section 11 & 14).
# --------------------------------------------------------------------------
AI_PROVIDER = env("AI_PROVIDER", default="anthropic")
AI_API_KEY = env("AI_API_KEY", default="")
AI_MODEL = env("AI_MODEL", default="claude-sonnet-4-6")

# Campus SSO. Empty means the button stays off. Licensed email still required after a token verifies.
GOOGLE_OAUTH_CLIENT_ID = env("GOOGLE_OAUTH_CLIENT_ID", default="")
MICROSOFT_OAUTH_CLIENT_ID = env("MICROSOFT_OAUTH_CLIENT_ID", default="")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
}

# --------------------------------------------------------------------------
# Email — people who are concerned by an action are mailed at the address
# on their ClubConnect account (or the address they typed on a public form).
# Set EMAIL_HOST to MailHog (127.0.0.1:1025) or the campus SMTP relay.
# Without EMAIL_HOST, DEBUG writes messages to var/mail/.
# --------------------------------------------------------------------------
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="ClubConnect <noreply@clubconnect.local>")
PUBLIC_APP_URL = env("PUBLIC_APP_URL", default="http://127.0.0.1:5173")
NOTIFICATION_CHANNELS = env.list("NOTIFICATION_CHANNELS", default=["in_app", "email"])
if env.bool("EMAIL_DISABLED", default=False):
    NOTIFICATION_CHANNELS = [name for name in NOTIFICATION_CHANNELS if name != "email"]
elif "email" not in NOTIFICATION_CHANNELS:
    NOTIFICATION_CHANNELS = [*NOTIFICATION_CHANNELS, "email"]
EMAIL_FILE_PATH = env("EMAIL_FILE_PATH", default=str(BASE_DIR / "var" / "mail"))
_email_backend = env("EMAIL_BACKEND", default="")
if _email_backend:
    EMAIL_BACKEND = _email_backend
elif EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
elif DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
    Path(EMAIL_FILE_PATH).mkdir(parents=True, exist_ok=True)
else:
    EMAIL_BACKEND = "django.core.mail.backends.dummy.EmailBackend"
