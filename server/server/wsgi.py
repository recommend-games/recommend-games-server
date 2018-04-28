"""
WSGI config for server project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.6/howto/deployment/wsgi/
"""

from server.boot import fix_path
fix_path()

import os
from django.core.wsgi import get_wsgi_application
from djangae.environment import is_production_environment
from djangae.wsgi import DjangaeApplication

settings = "server.settings_live" if is_production_environment() else "server.settings"
os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings)



application = DjangaeApplication(get_wsgi_application())
