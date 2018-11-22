# -*- coding: utf-8 -*-

''' admin settings '''

from django.conf import settings
from django.contrib import admin

from .models import Game, Person

if settings.DEBUG:
    admin.site.register(Game)
    admin.site.register(Person)
