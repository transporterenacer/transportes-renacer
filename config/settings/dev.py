from .base import *  # noqa: F401,F403

STORAGES = {
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

MIDDLEWARE = [
    m for m in MIDDLEWARE if "whitenoise" not in m.lower()
]
