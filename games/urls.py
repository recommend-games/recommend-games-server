# -*- coding: utf-8 -*-

''' URLs '''

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import CollectionViewSet, GameViewSet, PersonViewSet, UserViewSet

ROUTER = DefaultRouter()
ROUTER.register('games', GameViewSet)
ROUTER.register('persons', PersonViewSet)
ROUTER.register('users', UserViewSet)
ROUTER.register('collections', CollectionViewSet)

# pylint: disable=invalid-name
urlpatterns = [
    path('', include(ROUTER.urls)),
]
