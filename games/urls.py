# -*- coding: utf-8 -*-

''' URLs '''

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    CategoryViewSet, CollectionViewSet, GameViewSet, MechanicViewSet, PersonViewSet, UserViewSet)

ROUTER = DefaultRouter()
ROUTER.register('categories', CategoryViewSet)
ROUTER.register('collections', CollectionViewSet)
ROUTER.register('games', GameViewSet)
ROUTER.register('mechanics', MechanicViewSet)
ROUTER.register('persons', PersonViewSet)
ROUTER.register('users', UserViewSet)

# pylint: disable=invalid-name
urlpatterns = [
    path('', include(ROUTER.urls)),
]
