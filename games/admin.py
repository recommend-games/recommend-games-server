""" admin settings """

from django.conf import settings
from django.contrib import admin

from .models import Category, Collection, Game, GameType, Mechanic, Person, User

if settings.DEBUG:
    admin.site.register(Category)
    admin.site.register(Collection)
    admin.site.register(Game)
    admin.site.register(GameType)
    admin.site.register(Mechanic)
    admin.site.register(Person)
    admin.site.register(User)
