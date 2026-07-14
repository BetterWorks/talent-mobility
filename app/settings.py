import sys
from os import environ


LOG_LEVEL = environ.get('LOG_LEVEL', 'INFO')

APP_NAME = environ.get('APP_NAME', 'internal-mobility-matching')
APP_ENV = environ.get('APP_ENV', 'local')
APP_HOST = environ.get('APP_HOST', '0.0.0.0')
APP_PORT = int(environ.get('APP_PORT', 8000))

if 'pytest' in sys.modules:
    APP_ENV = 'test'
