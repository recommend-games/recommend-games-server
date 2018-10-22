# -*- coding: utf-8 -*-

''' admin settings '''

from django.contrib import admin

from .models import Game, Person

admin.site.register(Game)
admin.site.register(Person)
