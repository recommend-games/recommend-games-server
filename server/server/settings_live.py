# -*- coding: utf-8 -*-

'''settings'''

from __future__ import absolute_import, division, print_function, unicode_literals, with_statement

# pylint: disable=wildcard-import,unused-wildcard-import
from server.settings import *

SESSION_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 2592000 #30 days
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_SSL_REDIRECT = True

# Using a route that is caught by appengines app.yaml, be sure to collectstatic before
# doing a deploy
STATIC_URL = '/static/'

SECURE_REDIRECT_EXEMPT = [
    # App Engine doesn't use HTTPS internally, so the /_ah/.* URLs need to be exempt.
    # Django compares these to request.path.lstrip("/"), hence the lack of preceding /
    r"^_ah/"
]

DEBUG = False

MIDDLEWARE = list(MIDDLEWARE)
if 'google.appengine.ext.appstats.recording.AppStatsDjangoMiddleware' in MIDDLEWARE:
    MIDDLEWARE.remove('google.appengine.ext.appstats.recording.AppStatsDjangoMiddleware')
if 'matches.middleware.ProfileMiddleware' in MIDDLEWARE:
    MIDDLEWARE.remove('matches.middleware.ProfileMiddleware')
MIDDLEWARE = tuple(MIDDLEWARE)

# Remove unsafe-inline from CSP_STYLE_SRC. It's there in default to allow
# Django error pages in DEBUG mode render necessary styles
if "'unsafe-inline'" in CSP_STYLE_SRC:
    CSP_STYLE_SRC = list(CSP_STYLE_SRC)
    CSP_STYLE_SRC.remove("'unsafe-inline'")
    CSP_STYLE_SRC = tuple(CSP_STYLE_SRC)

# Add the cached template loader for the Django template system (not for Jinja)
for template in TEMPLATES:
    template['OPTIONS']['debug'] = False
    if template['BACKEND'] == 'django.template.backends.django.DjangoTemplates':
        # Wrap the normal loaders with the cached loader
        template['OPTIONS']['loaders'] = [
            ('django.template.loaders.cached.Loader', template['OPTIONS']['loaders'])
        ]
