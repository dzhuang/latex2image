"""
Settings that override the defaults
"""
import os
import tempfile

DEBUG = False

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(tempfile.mkdtemp(), '_tests_db.sqlite3'),
    }
}

LANGUAGE_CODE = 'en-us'

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'
    }
}
