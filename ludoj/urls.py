# -*- coding: utf-8 -*-

''' URLs '''

from django.contrib import admin
from django.urls import include, path

# pylint: disable=invalid-name
urlpatterns = [
    path('api/', include('games.urls')),
    path('api/', include('rest_framework.urls'), name='rest_framework'),
    path('admin/', admin.site.urls),
]
