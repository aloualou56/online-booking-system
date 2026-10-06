import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv
import dj_database_url

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.getenv('DEBUG', 'False') == 'True'  # Production default: False

# SECRET_KEY must be provided via the environment (.env). A throwaway key is
# only allowed in DEBUG mode so local development works out of the box.
SECRET_KEY = os.getenv('SECRET_KEY', '')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'insecure-dev-only-key-do-not-use-in-production'
    else:
        raise ImproperlyConfigured(
            'The SECRET_KEY environment variable is required when DEBUG is False. '
            'Generate one with: python -c "from django.core.management.utils import '
            'get_random_secret_key; print(get_random_secret_key())"'
        )

ALLOWED_HOSTS = [
    h.strip()
    for h in os.getenv('ALLOWED_HOSTS', '127.0.0.1,localhost,reserva.gr').split(',')
    if h.strip()
]

# In DEBUG mode, allow all hosts for easier local development
if DEBUG:
    ALLOWED_HOSTS = ['*']


INSTALLED_APPS = [
    'accounts.apps.AccountsConfig',
    'businesses.apps.BusinessesConfig',
    'bookings.apps.BookingsConfig',
    'payments.apps.PaymentsConfig',
    'reviews.apps.ReviewsConfig',
    'notifications.apps.NotificationsConfig',
    'reports.apps.ReportsConfig',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.sitemaps',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
]

SITE_ID = 1

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    # Removed Django's XFrameOptionsMiddleware - our custom middleware handles this
    'erantevou.middleware.SecurityHeadersMiddleware',  # Our custom middleware handles all security headers
]

ROOT_URLCONF = 'erantevou.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'erantevou.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

if os.getenv('DATABASE_URL'):
    DATABASES['default'] = dj_database_url.parse(
        os.getenv('DATABASE_URL'), conn_max_age=600
    )

# Custom User Model
AUTH_USER_MODEL = 'accounts.CustomUser'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'el'
TIME_ZONE = 'Europe/Athens'
USE_I18N = True
USE_TZ = True
USE_L10N = False
DATE_FORMAT = 'd/m/Y'
DATE_INPUT_FORMATS = ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d']
DATETIME_FORMAT = 'd/m/Y H:i'

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'accounts:redirect_after_login'
LOGOUT_REDIRECT_URL = 'landing'
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Stripe
STRIPE_PUBLIC_KEY = os.getenv('STRIPE_PUBLIC_KEY', '')
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')

# ClickSend SMS
CLICKSEND_USERNAME = os.getenv('CLICKSEND_USERNAME', '')
CLICKSEND_API_KEY = os.getenv('CLICKSEND_API_KEY', '')
CLICKSEND_SENDER_ID = os.getenv('CLICKSEND_SENDER_ID', 'reservagr')

# Site URL (for SMS links etc.)
SITE_URL = os.getenv('SITE_URL', 'http://127.0.0.1:8000')

# Celery (optional, for background tasks)
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = CELERY_BROKER_URL

# Security
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG

# CSRF Trusted Origins - for HTTPS origin checking
CSRF_TRUSTED_ORIGINS = [
    f'https://{h.strip()}'
    for h in os.getenv('ALLOWED_HOSTS', '127.0.0.1,localhost,reserva.gr').split(',')
    if h.strip() and h.strip() not in ['127.0.0.1', 'localhost', '*']
]

# In DEBUG mode, add local development origins
if DEBUG:
    CSRF_TRUSTED_ORIGINS.extend([
        'http://127.0.0.1:8000',
        'http://localhost:8000',
    ])

# X-Frame-Options: Handled entirely by our custom middleware
# Django's XFrameOptionsMiddleware has been removed from middleware stack

# Cross-business integration - Allow all domains for seamless integration
# No manual domain configuration required
ENABLE_CROSS_BUSINESS_ACCESS = True

# Allow cookies in cross-origin contexts for business integrations
CSRF_COOKIE_SAMESITE = None  # More permissive than False
SESSION_COOKIE_SAMESITE = None
CSRF_COOKIE_HTTPONLY = False  # Allow JavaScript access for widgets
SESSION_COOKIE_HTTPONLY = True  # Keep session cookies secure

# HSTS - Tell browsers to always use HTTPS (Cloudflare also enforces this)
# Only enable in production when not debugging
if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Content Security Policy - Balanced security for regular pages
# Embeddable endpoints (API, booking pages) skip CSP entirely via middleware
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'", "'unsafe-eval'",
                  "cdn.jsdelivr.net", "cdnjs.cloudflare.com", "*.googleapis.com")
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'",
                 "cdn.jsdelivr.net", "cdnjs.cloudflare.com", "fonts.googleapis.com")
CSP_FONT_SRC = ("'self'", "data:", "cdnjs.cloudflare.com",
                "fonts.gstatic.com", "fonts.googleapis.com")
CSP_IMG_SRC = ("'self'", "data:", "blob:", "*")
CSP_CONNECT_SRC = ("'self'", "*")  # Allow API calls

# Cancellation Policy thresholds (in hours)
CANCELLATION_FULL_REFUND_HOURS = 48
CANCELLATION_HALF_REFUND_HOURS = 24

# Email Configuration (Resend)
EMAIL_BACKEND = 'erantevou.email_backend.ResendEmailBackend'
RESEND_API_KEY = os.getenv('RESEND_API_KEY', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'Reserva <noreply@reserva.gr>')
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# Site URL for email links
SITE_URL = os.getenv('SITE_URL', 'https://reserva.gr')
