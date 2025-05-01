from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(os.path.join(BASE_DIR, '.env'))

PAYPAL_CLIENT_ID = os.getenv('PAYPAL_CLIENT_ID')
PAYPAL_CLIENT_SECRET = os.getenv('PAYPAL_CLIENT_SECRET')
EXCHANGE_RATE_API_KEY = os.getenv('EXCHANGE_RATE_API_KEY')

SECRET_KEY = 'django-insecure-your-secret-key-here'

DEBUG = True

ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    '*.ngrok-free.app',
    '83d5-35-190-204-197.ngrok-free.app',  # New URL
    '62f9-34-78-238-122.ngrok-free.app',   # Keep old for reference
    'd2fa-34-38-160-61.ngrok-free.app',
    '940d-34-38-255-246.ngrok-free.app',
    '5cb0-35-195-126-127.ngrok-free.app',
    '*.cloudshell.dev',
    '8000-cs-1045846920909-default.cs-europe-west1-iuzs.cloudshell.dev',
]
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'https://*.ngrok-free.app',
    'https://83d5-35-190-204-197.ngrok-free.app',  # New URL
    'https://62f9-34-78-238-122.ngrok-free.app',   # Keep old
    'https://d2fa-34-38-160-61.ngrok-free.app',
    'https://5cb0-35-195-126-127.ngrok-free.app',
    'https://940d-34-38-255-246.ngrok-free.app',
    'https://*.cloudshell.dev',
    'https://8000-cs-1045846920909-default.cs-europe-west1-iuzs.cloudshell.dev',
]
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'payments',
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

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'https://d2fa-34-38-160-61.ngrok-free.app',
    'https://*.ngrok-free.app',
    'https://*.cloudshell.dev',
]

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'debug.log',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}