# -*- coding: utf-8 -*-

''' admin settings '''

from django.conf import settings
from django.contrib import admin

from .models import Collection, Game, Person, User

if settings.DEBUG:
    admin.site.register(Game)
    admin.site.register(Person)
    admin.site.register(User)
    admin.site.register(Collection)
