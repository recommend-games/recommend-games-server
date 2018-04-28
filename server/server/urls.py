# -*- coding: utf-8 -*-

'''URLs'''

from __future__ import absolute_import, division, print_function, unicode_literals, with_statement

from django.conf import settings
from django.conf.urls import include, url
from django.conf.urls.static import static
from django.contrib.staticfiles.views import serve

from rest_framework_jwt.views import obtain_jwt_token, refresh_jwt_token
# from rest_framework.authtoken.views import obtain_auth_token

import session_csrf
session_csrf.monkeypatch()

from django.contrib import admin
admin.autodiscover()

urlpatterns = (
    # Examples:
    # url(r'^$', 'server.views.home', name='home'),
    url(r'^_ah/', include('djangae.urls')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^csp/', include('cspreports.urls')),
    url(r'^', include('rest_framework.urls', namespace='rest_framework')),
    url(r'^jwt', obtain_jwt_token),
    url(r'^jwt/refresh', refresh_jwt_token),
)

if settings.DEBUG:
    urlpatterns += tuple(static(settings.STATIC_URL, view=serve, show_indexes=True))
