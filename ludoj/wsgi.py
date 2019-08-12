# -*- coding: utf-8 -*-

""" WSGI """

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ludoj.settings")

# pylint: disable=invalid-name
application = get_wsgi_application()
