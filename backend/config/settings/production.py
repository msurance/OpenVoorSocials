import os

from .base import *  # noqa: F401, F403

DEBUG = False

SECRET_KEY = os.environ['SECRET_KEY']

ALLOWED_HOSTS = [os.environ.get('ALLOWED_HOSTS', 'social.open4.app')]

CSRF_TRUSTED_ORIGINS = [
    f"https://{os.environ.get('ALLOWED_HOSTS', 'social.open4.app')}",
]

# ---------------------------------------------------------------------------
# Security hardening
# ---------------------------------------------------------------------------

# Cloudflare handles TLS — no SSL redirect needed at Django level
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
