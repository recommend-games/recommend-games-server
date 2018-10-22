# -*- coding: utf-8 -*-

''' URLs '''

from django.contrib import admin
from django.urls import include, path

# pylint: disable=invalid-name
urlpatterns = [
    path('', include('games.urls')),
    path('', include('rest_framework.urls'), name='rest_framework'),
    path('admin/', admin.site.urls),
]
