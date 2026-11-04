import os

from .settings import *


if os.environ.get("DJANGO_TEST_POSTGRES") != "1":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "test_db.sqlite3",
        }
    }
MEDIA_ROOT = Path("/tmp/opencode/team-finder-test-media")
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
