# -*- coding: utf-8 -*-

''' URLs '''

from django.contrib import admin
from django.urls import include, path

# pylint: disable=invalid-name
urlpatterns = [
    path('/', include('games.urls')),
    path('admin/', admin.site.urls),
]
