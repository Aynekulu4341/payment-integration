from pathlib import Path
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY')  # Loads from .env

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0', '6061-34-78-109-88.ngrok-free.app']
CSRF_TRUSTED_ORIGINS = [
    'https://8080-cs-1045846920909-default.cs-europe-west1-iuzs.cloudshell.dev',
    'https://*.cloudshell.dev',
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',  # For djangorestframework
    'payments',  # Your custom app
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'community_funding.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'community_funding.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- Load API keys from .env ---
EXCHANGE_RATE_API_KEY = config('EXCHANGE_RATE_API_KEY')  # For USD-to-ETB conversion
TELEBIRR_APP_ID = config('TELEBIRR_APP_ID')  # Telebirr payment integration
TELEBIRR_APP_KEY = config('TELEBIRR_APP_KEY')  # Telebirr payment integration
PAYPAL_CLIENT_ID = config('PAYPAL_CLIENT_ID')  # PayPal payment integration
PAYPAL_CLIENT_SECRET = config('PAYPAL_CLIENT_SECRET')  # PayPal payment integration
PAYPAL_MODE = "sandbox"  # or "live"
