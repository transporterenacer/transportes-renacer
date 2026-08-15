from .base import *  # noqa: F401,F403

DEBUG = False
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "").split(",")  # noqa: F405
SECRET_KEY = os.environ["SECRET_KEY"]  # noqa: F405
