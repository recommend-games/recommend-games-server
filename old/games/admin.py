# -*- coding: utf-8 -*-

''' admin settings '''

from __future__ import absolute_import, division, print_function, unicode_literals, with_statement

from django.contrib import admin

from .models import Game

admin.site.register(Game)
