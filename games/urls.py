# -*- coding: utf-8 -*-

''' URLs '''

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import GameViewSet, PersonViewSet

ROUTER = DefaultRouter()
ROUTER.register('games', GameViewSet)
ROUTER.register('persons', PersonViewSet)

# pylint: disable=invalid-name
urlpatterns = [
    path('', include(ROUTER.urls)),
]
