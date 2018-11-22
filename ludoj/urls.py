# -*- coding: utf-8 -*-

''' URLs '''

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

# pylint: disable=invalid-name
urlpatterns = [
    path('api/', include('games.urls')),
    path('api/', include('rest_framework.urls'), name='rest_framework'),
]

if settings.DEBUG:
    urlpatterns.append(path('admin/', admin.site.urls))
