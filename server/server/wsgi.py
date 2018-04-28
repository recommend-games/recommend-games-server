# -*- coding: utf-8 -*-

'''WSGI'''

from __future__ import absolute_import, division, print_function, unicode_literals, with_statement

import os

from server.boot import fix_path
fix_path()

from django.core.wsgi import get_wsgi_application
from djangae.environment import is_production_environment
from djangae.wsgi import DjangaeApplication

from djangae.contrib.consistency.signals import connect_signals
connect_signals()

settings = "server.settings_live" if is_production_environment() else "server.settings"
os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings)

application = DjangaeApplication(get_wsgi_application())
