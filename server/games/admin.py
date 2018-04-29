# -*- coding: utf-8 -*-

'''admin settings'''

from __future__ import absolute_import

from django.contrib import admin

from .models import Game

admin.site.register(Game)
