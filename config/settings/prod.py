import os  # noqa: F401,F403

import dj_database_url  # noqa: F401,F403
from django.core.exceptions import ImproperlyConfigured  # noqa: F401,F403

from .base import *  # noqa: F401,F403

DEBUG = False
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "").split(",")  # noqa: F405
SECRET_KEY = os.environ["SECRET_KEY"]  # noqa: F405

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

DATABASES = {"default": dj_database_url.config(conn_max_age=600)}
if not DATABASES["default"].get("ENGINE"):
    raise ImproperlyConfigured("DATABASE_URL es obligatoria en producción.")
