import os

_BASE_DIR = os.path.dirname(
    os.path.abspath(os.path.join(os.path.abspath(__file__), os.pardir)))

# Test database, you need to override this for your instance.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(_BASE_DIR, 'db.sqlite3'),
    },
}
