from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ['*']

SECRET_KEY = 'local-dev-secret-key-not-for-production-use'

# Override BASE_URL for local development so image URLs resolve correctly
BASE_URL = 'http://localhost:8000'
