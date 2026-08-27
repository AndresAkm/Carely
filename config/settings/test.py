import os

from .base import *  # noqa: F401, F403

# Override database for testing — MariaDB Cloud does not grant CREATE DATABASE.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db_test.sqlite3',
    }
}

# Disable migrations for faster test setup.
# Django will create tables directly from models.


class DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = DisableMigrations()

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

DEFAULT_FILE_STORAGE = 'django.core.files.storage.InMemoryStorage'
